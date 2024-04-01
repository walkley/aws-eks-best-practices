import glob
import json
import os
import re
import sys
import boto3

bedrock = boto3.client(
  service_name='bedrock-runtime', 
  region_name="us-west-2"
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
下面<markdown>中的内容从原始Markdown文件中按段落分拆后需要翻译的Markdown内容片段：
<markdown>{{markdown_content}}</markdown>

请仔细阅读并识别上面的Markdown内容的格式和结构，按照系统提示词中的规则思考哪些内容需要翻译，哪些内容不需要翻译。
完成翻译后，请将翻译后的内容放在 <translated_markdown></translated_markdown> 中，不要输出其它与翻译无关的内容。
'''

# split the long text to chunks, split by paragraphs, each chunk should less than 2048 characters
def split_text(text, chunk_max_length = chunk_max_length):
    '''
    Splits a given text into chunks that do not exceed a specified maximum length.
    This function takes a string `text` and an integer `chunk_max_length` as inputs. 
    Each chunk attempts to contain as many complete paragraphs as possible without exceeding the `chunk_max_length`. 
    '''

    chunks = []
    current_chunk = ''
    for paragraph in text.split('\n\n'):
        if len(current_chunk) + len(paragraph) + 1 > chunk_max_length:
            chunks.append(current_chunk)
            current_chunk = ''
        current_chunk += paragraph + '\n\n'
    chunks.append(current_chunk)
    return chunks

def translate_chunk(markdown_content):
    # don't translate if the markdown content is empty(spaces or tabs, etc)
    if not markdown_content.strip(" \t\n"):
        return markdown_content

    uer_content = user_prompt.replace("{{markdown_content}}", markdown_content)
    messages = [
    {
        "role": "user",
        "content": uer_content
    },
    {
        "role": "assistant",
        "content": "<translated_markdown>"
    }]

    body = json.dumps({
        "max_tokens": 4096, 
        "temperature": 0.1,
        "anthropic_version": "bedrock-2023-05-31",
        "system": system_prompt,
        "messages":  messages
    })

    response = bedrock.invoke_model(body=body, modelId=modelId_Claude3_Sonnet)
    response_body = json.loads(response.get('body').read())
    translated_content = ""
    for line in response_body['content']:
        translated_content += line['text']

    translated_content = translated_content.rstrip("</translated_markdown>")
    translated_content = translated_content.strip(" \n")
    # replace half-width punctuation marks with full-width punctuation marks, such as: ", ' etc.
    translated_content = re.sub(chinese_comma_pattern, r'\1，', translated_content)
    translated_content = re.sub(chinese_colon_pattern, r'\1：', translated_content)
    return translated_content

def translate_file(markdown_file):
    """
    Translates the content of a markdown file into Chinese and saves the translated content into a new file.
    This function reads the content of the specified markdown file, splits the content into manageable chunks, 
        translates each chunk individually to avoid exceeding API limits or encountering memory issues, 
        and then concatenates all translated chunks. The translated content is saved in a new file within the same directory as the original file, 
        with the new file name having a '.zh.md' extension to indicate the translation language.
    """
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # split the content into chunks
    chunks = split_text(content)

    # translate each chunk
    translated_chunks = []
    for index, chunk in enumerate(chunks):
        percent = round(100*(index+1)/len(chunks))
        sys.stdout.write(f"\rtranslating: {markdown_file} [{percent}%]")
        sys.stdout.flush()
        translated_chunks.append(translate_chunk(chunk))

    sys.stdout.write(f"\rtranslating: {markdown_file} [done!]\n")
    sys.stdout.flush()

    # concat all translated chunks
    translated_content = '\n\n'.join(translated_chunks)

    # save the translated content to the same directory, file name format as *.zh.md
    translated_file = os.path.splitext(markdown_file)[0] + '.zh.md'
    with open(translated_file, 'w', encoding='utf-8') as f:
        f.write(translated_content)

def translate_directory(path):
    if os.path.isfile(path):
        translate_file(path)
        # print(f"translating {path}")
    elif os.path.isdir(path):
        for file_path in glob.glob(f"{path}/**/*.md", recursive=True):
            if not file_path.endswith(('.ko.md', '.zh.md')):
                translate_file(file_path)
                # print(f"translating {file_path}")
    else:
        print(f"Invalid path: {path}")

if __name__ == '__main__':
    path = os.getcwd()
    if len(sys.argv) > 1:
        path = sys.argv[1]
    translate_directory(path)
