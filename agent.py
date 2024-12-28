from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic import BaseModel, field_validator
from openai.types.chat.chat_completion_content_part_param import (
    ChatCompletionContentPartTextParam,
    ChatCompletionContentPartImageParam
)
import os
import shutil
from typing import List, Literal
from typing_extensions import Annotated
import asyncio
import json
import websockets

from api import LocalRobot

# API key loading code remains the same
api_key_fname = 'api_key.json'
if not os.path.exists(api_key_fname):
    shutil.copy(api_key_fname + '.template', api_key_fname)
    print('api_key.json created, please paste API key into it. You should have "OPENROUTER_API_KEY": "<KEY>"')
    exit(1)

with open(api_key_fname) as f:
    try:
        api_key = json.load(f)["OPENROUTER_API_KEY"]
        if "paste" in api_key:  # still set to paste_key_here
            raise KeyError
        else:
            print('API key loaded successfully')
    except KeyError:
        print('Please paste your API key into api_key.json. You should have "OPENROUTER_API_KEY": "<KEY>"')
        exit(1)

class Models:
    llama90b = 'meta-llama/llama-3.2-90b-vision-instruct'
    novalite = 'amazon/nova-lite-v1'
    novapro = 'amazon/nova-pro-v1'
    qwenvl = 'qwen/qwen-2-vl-72b-instruct'
    gemini = 'google/gemini-flash-1.5'
    claude = 'anthropic/claude-3.5-sonnet'

class CommandType(BaseModel):
    type: Literal["move", "rotate"]
    magnitude: float

    @field_validator('magnitude')
    @classmethod
    def validate_magnitude(cls, value, values):
        if value is None:
            raise ValueError('Magnitude must be a float, not None')
        print(f"Validation: {value=}, {values=}")
        command_type = values.data.get('type')
        if command_type == 'move':
            if not (-1 <= value <= 1):
                raise ValueError('Move magnitude must be between 0 and 1')
        elif command_type == 'rotate':
            if not (-180 <= value <= 180):
                raise ValueError('Rotation magnitude must be between -180 and 180 degrees')
        return value

class ResponseType(BaseModel):
    image_desc: str
    explanation: str
    command: CommandType


class AgentServer:
    def __init__(self, host='0.0.0.0', port=3001):
        self.host = host
        self.port = port
        self.robot = LocalRobot()
        self.num_images = 1
        self.num_logs = 8
        self.images = []
        self.logs = ['<START>']
        self.connected_clients = set()
        self.running = False
        self.image_str = ''

        self.prev_img = ''
        self.prev_note = ''
        self.prev_dist = 0
        self.prev_action = ''

        # Initialize the model and agent
        self.model = OpenAIModel(
            model_name=Models.claude,
            base_url='https://openrouter.ai/api/v1',
            api_key=api_key
        )
        
        target = 'microscope'
        self.agent = Agent(
            self.model,
            system_prompt=f'You are driving a small robot car. Based on the most recent image and your logs from'
                          f'past actions, your goal is to find the {target} and drive into it (you won\'t hurt it).'
                          f'If the image is very unclear and you can\'t make anything out, it means'
                          f'that you\'re very close to something and should reverse or rotate.'
                          f'Make sure to move instead of just rotating - if you\'ve rotated 2 or 3 times in a'
                          f'row you should probably pick a direction to move. If you want to rotate towards something'
                          f'you can see, do it in small increments, like 20deg.',
            result_type=ResponseType,
            result_tool_description='The only thing you should do is call this tool. The first argument is a basic image description that you generate. Should be 5-10 words.'
                                    'The second argument is your explanation for why you are taking a certain action. Avoid obstacles at all costs.'
                                    'The third argument is the action you want the robot to take: "move" or "rotate", and a magnitude.'
                                    'Magnitude is in meters for movement and in degrees for rotation. Never move (in either direction) more than 1m or 180 deg.'
                                    'Positive movement is forward and negative is backward. Positive rotation is right / cw and negative is left / ccw.'
                                    'Note that you always have to select a magnitude in addition to movement type. You can rotate +/-90 deg and move +/-1m as a standard.'
                                    'Example: {"image_desc": "<image_desc>", "explanation": "<explanation>", command: {"type": "rotate", "magnitude": -90}} (this would be CCW - camera pans left)',
        )

    async def handle_client(self, websocket):
        """Handle individual client connections"""
        print(f"Client connected from {websocket.remote_address}")
        self.connected_clients.add(websocket)
        try:
            while True:
                await asyncio.sleep(0.1)  # Prevent busy waiting
        except websockets.exceptions.ConnectionClosed:
            print(f"Client disconnected from {websocket.remote_address}")
        finally:
            self.connected_clients.remove(websocket)

    async def broadcast_to_clients(self, message):
        """Broadcast message to all connected clients if any exist"""
        if not self.connected_clients:
            return
            
        websockets_tasks = []
        for websocket in self.connected_clients:
            websockets_tasks.append(asyncio.create_task(
                websocket.send(json.dumps(message))
            ))
        if websockets_tasks:
            await asyncio.gather(*websockets_tasks)

    async def run_agent(self, b64image: str, sensor_dist: float):
        """Run the agent with current image and sensor data"""
        print('Running agent...')

        self.image_str = f"data:image/jpeg;base64,{b64image}"
        
        # Only broadcast if there are connected clients
        # if self.connected_clients:
        #     await self.broadcast_to_clients({"image": image_str,
        #                                      "dist":})
        
        self.images.append(
            ChatCompletionContentPartImageParam(
                type='image_url',
                image_url={'url': self.image_str, 'detail': 'low'}
            )
        )
        if len(self.images) > self.num_images:
            self.images.pop(0)
        while True:
            try:
                result = await self.agent.run([
                    # ChatCompletionContentPartTextParam(
                    #     type='text',
                    #     # text=f'Distance to surface: {sensor_dist/100:.2f} m {"(Rotate!)" if sensor_dist < 100 else ""}\nLogs: {self.logs}'
                    #     text=f'Logs: {self.logs}'
                    # ),
                    *self.images
                ])
                break
            except UnexpectedModelBehavior as e:
                print(f'Model error: {e}')
                continue
        self.logs.append(result.data)
        print(result.data)
        if len(self.logs) > self.num_logs:
            self.logs.pop(0)
            # print(f'Snipped log, new log: {self.logs}')
            # print(f'Snipped log, new log: {self.logs}')

        return result.data

    async def main_loop(self):
        """Main agent loop that runs independently of websocket connections"""
        self.running = True
        while self.running:
            dist = self.robot.get_distance()
            result: ResponseType = await self.run_agent(
                b64image=self.robot.get_current_frame(),
                sensor_dist=dist
            )
            
            # Execute the command
            if result.command.type == 'move':
                await self.robot.move_dist(dist=result.command.magnitude)
            elif result.command.type == 'rotate':
                await self.robot.rotate_deg(degrees=result.command.magnitude)
            else:
                print('Unknown command:', result.command)
            


            # Broadcast result to any connected clients
            await self.broadcast_to_clients({
                "image": self.image_str,
                # "dist": dist,
                # Below is generated by LLM
                "desc": result.image_desc,
                "move": f'{result.command.type} {result.command.magnitude:.1f} {"m" if result.command.type == "move" else "deg"}',
                "notes": result.explanation,
            })
            
            await asyncio.sleep(1)  # Wait for image/sensor to stabilize

    async def start(self):
        """Start both the websocket server and main agent loop"""
        main_loop = asyncio.create_task(self.main_loop())
        
        # Start websocket server
        websocket_server = await websockets.serve(self.handle_client, self.host, self.port)
        print(f"WebSocket server started on ws://{self.host}:{self.port}")
        
        try:
            # Run both the main loop and websocket server concurrently
            await asyncio.gather(
                main_loop,
                asyncio.Future()  # Keep the websocket server running
            )
        finally:
            self.running = False
            websocket_server.close()
            await websocket_server.wait_closed()

async def main():
    server = AgentServer()
    await server.start()

if __name__ == '__main__':
    asyncio.run(main())