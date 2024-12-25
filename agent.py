from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic import BaseModel
from openai.types.chat.chat_completion_content_part_param import (
    ChatCompletionContentPartTextParam,
    ChatCompletionContentPartImageParam
)
import os
import shutil
from typing import List, Literal
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

class ResponseType(BaseModel):
    command: Literal["forward", "reverse", "rot_right", "rot_left"]
    notes: str

class AgentServer:
    def __init__(self, host='localhost', port=3001):
        self.host = host
        self.port = port
        self.robot = LocalRobot()
        self.num_images = 1
        self.num_logs = 5
        self.images = []
        self.logs = ['<START>']
        self.connected_clients = set()
        self.running = False
        
        # Initialize the model and agent
        self.model = OpenAIModel(
            model_name=Models.gemini,
            base_url='https://openrouter.ai/api/v1',
            api_key=api_key
        )
        
        target = 'parrot statue'
        self.agent = Agent(
            self.model,
            system_prompt=f'You are driving a robot car. Based on the most recent image, your distance'
                        f'sensor (the distance to the nearest object in front of you), and your'
                        f'logs from past movement cycles, move around the room to find the {target}.'
                        f'You move by sending api commands as described in the tool description.'
                        f'Make sure to avoid obstacles! DO NOT move forward if something is very close'
                        f'in front of you. If you get too close to something, either back up or'
                        f'rotate. Use the distance sensor but it\'s not very reliable so be cautious.'
                        f'When something is less than 1m away either reverse or rotate because you'
                        f'will hit it if you move forward.',
            result_type=ResponseType,
            result_tool_description='First argument is the movement command. Forward'
                                  'and reverse move about 1m. Rotating does about 45 deg. The second'
                                  'argument is a short sentence describing your goal in moving -'
                                  'where you want to get to and how this movement helps that, etc.'
                                  'Example call: {"command": "forward", "notes": "Moving towards doorway"}'
        )

    async def handle_client(self, websocket, path):
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
        print(f'Running agent, dist= {sensor_dist / 100:.0f} m')
        image_str = f"data:image/jpeg;base64,{b64image}"
        
        # Only broadcast if there are connected clients
        if self.connected_clients:
            await self.broadcast_to_clients({"image": image_str})
        
        self.images.append(
            ChatCompletionContentPartImageParam(
                type='image_url',
                image_url={'url': image_str, 'detail': 'low'}
            )
        )
        if len(self.images) > self.num_images:
            self.images.pop(0)
            
        print('Running agent...')
        result = await self.agent.run([
            ChatCompletionContentPartTextParam(
                type='text',
                text=f'Distance to surface: {sensor_dist/100:.2f} m {"(Don't move forward!)" if sensor_dist < 100 else ""}\nLogs: {self.logs}'
            ),
            *self.images
        ])
        self.logs.append(result.data)
        print(result.data)
        if len(self.logs) > self.num_logs:
            self.logs.pop(0)

        return result.data

    async def main_loop(self):
        """Main agent loop that runs independently of websocket connections"""
        self.running = True
        while self.running:
            result: ResponseType = await self.run_agent(
                b64image=self.robot.get_current_frame(),
                sensor_dist=self.robot.get_distance()
            )
            
            # Execute the command
            if result.command == 'forward':
                await self.robot.forward()
            elif result.command == 'reverse':
                await self.robot.reverse()
            elif result.command == 'rot_right':
                await self.robot.rotate_right()
            elif result.command == 'rot_left':
                await self.robot.rotate_left()
            else:
                print('Unknown command:', result.command)
                
            # Broadcast result to any connected clients
            await self.broadcast_to_clients({
                "status": "success",
                "command": result.command,
                "notes": result.notes
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