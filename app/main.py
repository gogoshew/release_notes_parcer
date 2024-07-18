import os
import shutil
import yaml
import requests
import re
from datetime import datetime
import json

url_stage = 'http://sapi-docs-ingress-controller.sapi-docs.k8s.stage-xc/api/v1/admin/release_notes'

replinks = []

scopes = {
    'general': 'api-information',
    'content': 'work-with-products',
    'prices': 'work-with-products',
    'supplies': 'orders-fbw',
    'marketplace': 'orders-fbs',
    'statistics': 'reports',
    'analytics': 'analytics',
    'promotion': 'promotion',
    'recommendations': 'work-with-products',
    'feedbacks-questions': 'user-communication',
    'tariffs': 'wb-tariffs',
    'buyers-chat': 'user-communication',
    'returns': 'user-communication',
}


def send_post_request(url, data):
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=data, headers=headers)
        resp.raise_for_status()
        resp_data = resp.json()

        print(f"Response OK, SCOPE - {data['scope'][0]} {resp_data.get('header')}")
        return resp.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {resp.request.body}")
        print(f"Response content: {resp.text}")
    except Exception as err:
        print(f"An error occurred: {err}")


def find_and_copy_yaml_files(root_dir, output_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if 'releasenotes' in dirnames:
            release_notes_path = os.path.join(dirpath, 'releasenotes')
            for filename in os.listdir(release_notes_path):
                if filename == 'releasenotes.yaml':
                    parent_folder_name = os.path.basename(dirpath)
                    new_filename = f"{parent_folder_name}.yaml"
                    yaml_file_path = os.path.join(release_notes_path, filename)
                    output_file_path = os.path.join(output_dir, new_filename)
                    shutil.copy(yaml_file_path, output_file_path)
                    print(f"Copied {yaml_file_path} to {output_file_path}")


def load_yaml_to_dict(yaml_file_path):
    with open(yaml_file_path, 'r', encoding='utf-8') as file:
        try:
            yaml_content = yaml.safe_load(file)
            return yaml_content
        except yaml.YAMLError as exc:
            print(f"Error reading YAML file {yaml_file_path}: {exc}")
            return {}


def convert_text_to_string(content):
    res = []

    def process_content(block):
        if isinstance(block, str):
            res.append("- " + block)
            # if 'REPLINK' in block:
                # collect_links(replinks, block)
        elif isinstance(block, list):
            for item in block:
                process_content(item)
        elif isinstance(block, dict):
            for key, value in block.items():
                key = key + " "
                process_content(key)
                process_content(value)

    process_content(content)
    return "\n\t".join(res)


def format_data(filename: str, yaml_slice: list) -> list:
    res = []
    date_format = "%d.%m.%Y"
    actual_date = datetime.strptime("08.05.2024", date_format)
    for note in yaml_slice:
        formatted_date = datetime.strptime(note.get('date_publish', ""), date_format)
        ru_text = fix_tags(convert_text_to_string(note.get('text', "").get('ru', "")))
        en_text = fix_tags(convert_text_to_string(note.get('text', "").get('en', "")))
        cn_text = fix_tags(convert_text_to_string(note.get('text', "").get('cn', "")))
        if formatted_date < actual_date:
            ru_text = remove_anchor_tags(ru_text)
            en_text = remove_anchor_tags(en_text)
            cn_text = remove_anchor_tags(cn_text)
        else:
            ru_text = replace_link(ru_text, 'ru')
            en_text = replace_link(en_text, 'en')
            cn_text = replace_link(cn_text, 'cn')

        data = {
            "header": note.get('title', "").get('ru', ""),
            "text": ru_text,
            "status": "RELEASE_NOTE_STATUS_PUBLISHED",
            "date": datetime.strptime(note.get('date_publish', ""), date_format).strftime("%Y-%m-%d") + "T00:00:00Z",
            "mainTag": "RELEASE_NOTE_MAIN_TAG_MINOR",
            "scope": [scopes.get(filename.split('.')[0], "")],
            "type": "RELEASE_NOTE_TYPE_NEW",
            "localizedHeaders": {
                'ru': note.get('title', "").get('ru', ""),
                'en': note.get('title', "").get('en', ""),
                'cn': note.get('title', "").get('cn', ""),
            },
            "localizedTexts": {
                'ru': ru_text,
                'en': en_text,
                'cn': cn_text,
            }
        }
        res.append(data)

    return res


def process_yaml_files_in_directory(directory):
    yaml_files_data = []
    for filename in os.listdir(directory):
        if filename.endswith('.yaml'):
            yaml_file_path = os.path.join(directory, filename)
            yaml_dict = load_yaml_to_dict(yaml_file_path)
            for data in format_data(filename, yaml_dict.get('releasenotes', "")):
                # send_post_request(url_stage, data)
                print(data)
                pass
    return yaml_files_data


def fix_tags(text):
    pattern = r'<a\s+([^>]*?)(?=\s*>)'

    def replacement(match):
        attributes = match.group(1).strip()
        if 'href=' in attributes:
            return f'<a {attributes}'
        href_value = attributes
        return f'<a href="{href_value}'

    fixed_text = re.sub(pattern, replacement, text)
    fixed_text = fixed_text.replace('<br>', '<br />')
    fixed_text = fixed_text.replace('<makr>', '<code>')
    fixed_text = fixed_text.replace('<code>{', '<code>&#123;')
    fixed_text = fixed_text.replace('}</code>', '&#125;</code>')
    fixed_text = fixed_text.replace('<a class', '<a className')

    return fixed_text


def remove_anchor_tags(text):
    pattern = r'<a\s+[^>]*>(.*?)</a>'
    return re.sub(pattern, r'\1', text)


def replace_link(text, locale):
    pattern = r'<a href="REPLINK/(.*?)"'
    replacement = fr'<a href="/{locale}/openapi/\1"'
    output_string = re.sub(pattern, replacement, text)
    return output_string

# def collect_links(res: list, link: str):
#     match = re.search(r'(<a [^>]+>)', link)
#     if match:
#         res = res.append(match.group(1))
#     else:
#         return None
#     return res
#
#
# def create_and_write_json(file_name):
#     with open(file_name, 'w') as file:
#         json.dump([], file)
#
#
# def append_to_json(file_name, lines):
#     with open(file_name, 'r') as file:
#         data = json.load(file)
#
#     for line in lines:
#         data.append(line)
#
#     with open(file_name, 'w') as file:
#         json.dump(data, file, indent=4)


if __name__ == "__main__":
    root_directory = "/Users/iabalymov/GolandProjects/docs-v2"
    output_directory = "../src"

    # if not os.path.exists(output_directory):
    #     os.makedirs(output_directory)
    #
    # find_and_copy_yaml_files(root_directory, output_directory)

    release_notes = process_yaml_files_in_directory(output_directory)
    # create_and_write_json('replinks.json')
    # append_to_json('replinks.json', replinks)

