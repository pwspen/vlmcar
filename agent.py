from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic import BaseModel
from openai.types.chat.chat_completion_content_part_param import (
    ChatCompletionContentPartTextParam,
    ChatCompletionContentPartImageParam
)
from openai.types.chat.chat_completion_content_part_image_param import (
    ImageURL
)
import os
import shutil
from typing import List, Literal
import asyncio
import json

from api import LocalRobot

api_key_fname = 'api_key.json'
if not os.path.exists(api_key_fname):
    shutil.copy(api_key_fname + '.template', api_key_fname)
    print('api_key.json created, please paste API key into it. You should have "OPENROUTER_API_KEY": "<KEY>"')
    exit(1)

with open(api_key_fname) as f:
    try:
        api_key = json.load(f)["OPENROUTER_API_KEY"]
        if "paste" in api_key: # still set to paste_key_here
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

model = OpenAIModel(
    model_name=Models.gemini,
    base_url='https://openrouter.ai/api/v1',
    api_key=api_key
)
target = 'parrot statue'
agent = Agent(model,
              system_prompt=f'You are driving a robot car. Based on the most recent image, your distance'
                            f'sensor (the distance to the nearest object in front of you), and your'
                            f'logs from past movement cycles, move around the room to find the {target}.'
                            f'You move by sending api commands as described in the tool description.'
                            f'Make sure to avoid obstacles! DO NOT move forward if something is very close'
                            f'in front of you. If you get too close to something, either back up or'
                            f'rotate. Use the distance sensor but it\'s not very reliable so be cautious.',
              result_type=ResponseType,
              result_tool_description='First argument is the movement command. Foward'
                                      'and reverse move about 1m. Rotating does about 45 deg. The second'
                                      'argument is a short sentence describing your goal in moving -'
                                      'where you want to get to and how this movement helps that, etc.'
                                      'Example call: {"command": "forward", "notes": "Moving towards doorway"}')

class AgentContainer:
    def __init__(self):
        self.robot = LocalRobot()
        self.num_images = 1
        self.num_logs = 5
        self.images = []
        self.logs = ['<START>']

    async def run_agent(self, agent, b64image: str, sensor_dist: float):
        print(f'Running agent, dist= {sensor_dist}')
        self.images.append(
            ChatCompletionContentPartImageParam(
                type='image_url',
                image_url={'url': f"data:image/jpeg;base64,{b64image}", 'detail': 'low'}
            )
        )
        if len(self.images) > self.num_images:
            self.images.pop(0)
        print('Sending server request..')
        result = await agent.run([
            ChatCompletionContentPartTextParam(
                type='text',
                text=f'Distance to surface: {sensor_dist}\nLogs: {self.logs}'
            ),
            *self.images
        ])
        self.logs.append(result.data)
        print(result.data)
        if len(self.logs) > self.num_logs:
            self.logs.pop(0)

        return result.data

    async def loop(self):
        result: ResponseType = await self.run_agent(agent, 
                                       b64image=self.robot.get_current_frame(),
                                       sensor_dist=self.robot.get_distance())
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
        await asyncio.sleep(1) # Wait a bit for image/sensor to stabilize

if __name__ == '__main__':
    container = AgentContainer()
    while True:
        asyncio.run(container.loop())