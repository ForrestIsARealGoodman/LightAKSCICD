import re
import os
import zipfile
import base64


def check_var_substr(value):
    pattern_with_dollar = re.compile(r"^\$\{\{\s*\w+\s*\}\}")
    pattern_with_quotes = re.compile(r"^\{\{\s*\w+\s*\}\}")
    if pattern_with_dollar.match(value) or pattern_with_quotes.match(value):
        print(f"{value} match")
        return True
    else:
        print(f"{value} does not match")
        return False


def get_var_substr(value):
    regex_pattern = r"\w+"
    match = re.search(regex_pattern, value)
    return match[0].strip()


class Quoted(str):
    pass


class Literal(str):
    pass


def quoted_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')


def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


def ordered_dict_presenter(dumper, data):
    return dumper.represent_dict(data.items())


# use for decode and debug intermittent resource yaml zip context
# before use it, plz copy the context from jenkins logs and paste into a file
def dump_zip_context(resource_context_file):
    resource_dir = "resource"
    if not os.path.exists(resource_dir):
        os.makedirs(resource_dir)
    with open(resource_context_file, "r") as resource_reader:
        content_str = resource_reader.read()
        zip_file = base64.b64decode(content_str)
        resource_zip = r"{0}\{1}.zip".format(resource_dir, resource_dir)
        with open(resource_zip, 'wb') as zip_writer:
            zip_writer.write(zip_file)
    with zipfile.ZipFile(resource_zip, 'r') as zip_ref:
        zip_ref.extractall(resource_dir)


if __name__ == '__main__':
    dump_zip_context(r"config\read_file.txt")

