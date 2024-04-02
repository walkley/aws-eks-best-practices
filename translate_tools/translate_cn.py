import glob
import json
import logging
import os
import re
import sys
import time
import boto3
from botocore.client import Config as BotoConfig

logger = logging.getLogger(__name__)
logging.StreamHandler(sys.stdout)
h1 = logging.StreamHandler(sys.stdout)
h1.setLevel(logging.DEBUG)
logger.addHandler(h1)
logger.setLevel(logging.DEBUG)

TIMEOUT = 300
config = BotoConfig(read_timeout=TIMEOUT, connect_timeout=TIMEOUT, retries={"max_attempts": 3})
bedrock = boto3.client(
  service_name='bedrock-runtime', 
  region_name="us-west-2",
  config = config
)

modelId_Claude3_Sonnet = 'anthropic.claude-3-sonnet-20240229-v1:0'
modelId_Claude3_Haiku = "anthropic.claude-3-haiku-20240307-v1:0"
chinese_comma_pattern = r'([\u4e00-\u9fa5]+[\w )]*),'
chinese_colon_pattern = r'([\u4e00-\u9fa5]+[\w )]*):'
chunk_max_length = 2048

system_prompt = '''
你是一位AWS资深解决方案架构师，同时精通英文和中文，也非常熟悉Markdown文件的格式。你正在协助用户将Markdown格式的英文技术文档翻译成简体中文，请在协助翻译时严格遵守以下规则：
- 翻译后的中文格式需精确对应原 Markdown 文件，包含标题、代码块、列表等。
- 必须保证中文翻译的自然、精确以及流畅。
- 对于代码块、json、XML、HTML 及其他只为计算机展示或执行的内容，这类内容不要翻译，原样复制过来即可。
- 被双引号括住的单词或句子，像 "Version"之类，无需翻译。
- 一些罕见或译后不自然的专业术语，如 "Spot"，也需保持原样，不进行翻译。
- 原始英文是Markdown的片段，可能结构不完整或不合理，但请不要擅自扩展或修改任何格式以及内容，也不要删除任何看上去不适合的内容，严格按照原始格式和内容翻译。
- 翻译后的内容无需在开头和结尾添加任何回车或空格，以确保其与原始英文内容的完全一致。
'''

user_prompt = '''
下面<markdown>中的内容从原始Markdown文件中读取的内容：
<markdown>{{markdown_content}}</markdown>

请仔细阅读并识别上面的Markdown内容的格式和结构，按照系统提示词中的规则思考哪些内容需要翻译，哪些内容不需要翻译。
完成翻译后，请将翻译后的内容放在 <translated_markdown></translated_markdown> 中，不要输出其它与翻译无关的内容。
'''

def complete_translation(system_prompt: str, user_content: str, translated_content: str, modelId=modelId_Claude3_Haiku):
    '''
    Complete translation by sending the already translated part to prefill the assistant, assistant should continue to translate the remaining content.
    '''
    messages = [
    {
        "role": "user",
        "content": user_content
    },
    {
        "role": "assistant",
        "content": translated_content.rstrip() #final assistant content cannot end with trailing whitespace
    }]

    body = json.dumps({
        "max_tokens": 4096, 
        "temperature": 0.1,
        "anthropic_version": "bedrock-2023-05-31",
        "system": system_prompt,
        "messages":  messages
    })
    response = bedrock.invoke_model(body=body, modelId=modelId)
    response_body = json.loads(response.get('body').read())

    return response_body
    
def translate_file(markdown_file):
    # check file size > 100k
    if os.path.getsize(markdown_file) > 100000:
        logger.error(f"{markdown_file} is larger than 100k which cannot be handled")
        return

    start_time = time.time()
    logger.info(f"translating {markdown_file} ...")
    with open(markdown_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    uer_content = user_prompt.replace("{{markdown_content}}", markdown_content)
    translated_content = "<translated_markdown>"
    total_input_tokens = 0
    total_output_tokens = 0
    while True:
        response_body = complete_translation(system_prompt, uer_content, translated_content)
        for line in response_body['content']:
            translated_content += line['text']
        
        input_tokens = response_body.get('usage').get('input_tokens')
        output_tokens = response_body.get('usage').get('output_tokens')
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        logger.info(f"    completed one trunk, input_tokens: {input_tokens}, output_tokens: {output_tokens}")
        # break the loop(stop translation) if stop_reason is "end_turn" or translated_content contains "</translated_markdown>"
        if response_body.get('stop_reason') == "end_turn" or "</translated_markdown>" in translated_content:
            break
    
    translated_content = translated_content.strip()
    if translated_content.startswith("<translated_markdown>") and translated_content.endswith("</translated_markdown>"):
        translated_content = translated_content[len("<translated_markdown>"):-len("</translated_markdown>")].strip()
        # replace half-width punctuation marks with full-width punctuation marks, such as: ", ' etc.
        translated_content = re.sub(chinese_comma_pattern, r'\1，', translated_content)
        translated_content = re.sub(chinese_colon_pattern, r'\1：', translated_content)
        translated_file = os.path.splitext(markdown_file)[0] + '.zh.md'
        with open(translated_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        logger.info(f"done! [{int(time.time() - start_time)}s], consumed tokens: input = {total_input_tokens}, output = {total_output_tokens}")
    else:
        logger.error(f"Error: {markdown_file} translation failed")

def translate(path):
    if os.path.isfile(path):
        translate_file(path)
    elif os.path.isdir(path):
        for file_path in glob.glob(f"{path}/**/*.md", recursive=True):
            if not file_path.endswith(('.ko.md', '.zh.md')):
                translate_file(file_path)
    else:
        logger.error(f"Invalid path: {path}")

if __name__ == '__main__':
    path = os.getcwd()
    if len(sys.argv) > 1:
        path = sys.argv[1]
    translate(path)
