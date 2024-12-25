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

class Models:
    llama90b = 'meta-llama/llama-3.2-90b-vision-instruct'
    novalite = 'amazon/nova-lite-v1'
    novapro = 'amazon/nova-pro-v1'
    qwenvl = 'qwen/qwen-2-vl-72b-instruct'

class ResponseType(BaseModel):
    command: Literal["forward", "reverse", "rot_right", "rot_left"]
    notes: str

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
    except KeyError:
        print('Please paste your API key into api_key.json. You should have "OPENROUTER_API_KEY": "<KEY>"')
        exit(1)

model = OpenAIModel(
    model_name=Models.qwenvl,
    base_url='https://openrouter.ai/api/v1',
    api_key=api_key
)
target = 'parrot statue'
agent = Agent(model,
              system_prompt=f'You are driving a robot car. Based on the most recent image, your distance'
                            f'sensor (the distance to the nearest object in front of you), and your'
                            f'logs from past movement cycles, move around the room to find the {target}.'
                            f'You move by sending api commands as described in the tool description.',
              result_type=ResponseType,
              result_tool_description='First argument is the movement command. Foward'
                                      'and reverse move about 1m. Rotating does about 45 deg. The second'
                                      'argument is a short sentence describing your goal in moving -'
                                      'where you want to get to and how this movement helps that, etc.'
                                      'Example call: {"command": "forward", "notes": "Moving towards doorway"}')

num_images = 3
num_logs = 3
images = []
logs = ['<START>']
async def run_agent(agent, b64image: str, sensor_dist: float):
    images.append(
        ChatCompletionContentPartImageParam(
            type='image_url',
            image_url={'url': f"data:image/jpeg;base64,{b64image}", 'detail': 'low'}
        )
    )
    if len(images) > num_images:
        images.pop(0)
    result = await agent.run([
        ChatCompletionContentPartTextParam(
            type='text',
            text=f'Distance from sensor: {sensor_dist}\nLogs: {logs}'
        ),
        *images
    ])
    logs.append(result.data)
    print(result.data)
    if len(logs) > num_logs:
        logs.pop(0)


if __name__ == '__main__':
    robot = LocalRobot()
    while True:
        asyncio.run(run_agent(agent, 
                              b64image=robot.get_current_frame(),
                              sensor_dist=robot.get_distance()
                              ))