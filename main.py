import datetime

import secret
import re
import os
import git


class ObjectTree:
    def __init__(self):
        self.path_to_repo = secret.path_to_repo()
        self.name_of_src = secret.name_of_configuration()
        self.date_since = datetime.datetime(2016, 1, 1)
        self.configuration_name = ''
        self.subsystems = []
        self.commits = []

    def print_obj(self):
        spacer = '  '
        print(self.configuration_name)
        if len(self.subsystems) > 0:
            print(spacer + 'Подсистемы')
            count = 1
            for subsystem in self.subsystems:
                self.print_subsystem(subsystem, count, spacer)

    def print_subsystem(self, subsystem, count, spacer):
        count += 1
        for info in subsystem:
            print(spacer * count + info)
            count += 1
            if len(subsystem.get(info).get('subsystems')) > 0:
                print(spacer * count + 'Подсистемы')
                for inner_subsystem in subsystem.get(info).get('subsystems'):
                    count += 1
                    self.print_subsystem(inner_subsystem, count, spacer)
                    count -= 1

            print(spacer * count + 'Объекты')
            for content in subsystem.get(info).get('contents'):
                print(spacer * (count + 1) + content)

    def get_commits_info(self):
        repo = git.Repo(self.path_to_repo)
        commits = list(repo.iter_commits("master"))
        for commit in commits:
            if commit.committed_datetime.timestamp() <= self.date_since.timestamp():
                break
            for file in commit.stats.files:
                # find only in chosen configuration in secret and .bsl files
                if file.startswith(self.name_of_src + 'src/') and file.endswith('bsl'):
                    stat = {'date': commit.committed_datetime.date(),
                            'file': file,
                            'insert': commit.stats.files.get(file).get('insertions'),
                            'delete': commit.stats.files.get(file).get('deletions'),
                            'author': commit.author.name,
                            'email': commit.author.email}
                    # print(stat)
                    self.commits.append(stat)

    def summurize_info_to_contents(self):
        summurized = {}
        if len(self.commits) == 0:
            return
        for commit in self.commits:
            file = commit.get('file')
            email = commit.get('email')
            file_info = summurized.get(file)
            if file_info is None:
                file_info = {email: {'insert': 0, 'delete': 0}}
            email_info = file_info.get(email)
            if email_info is None:
                email_info = {'insert': 0, 'delete': 0}
            email_info.update({'insert': email_info.get('insert') + commit.get('insert')})
            email_info.update({'delete': email_info.get('delete') + commit.get('delete')})
            file_info.update({email: email_info})
            summurized.update({file: file_info})

        print(summurized)


def path_to_object(content):
    parts_of_name = content.split('.')
    if content.startswith('FilterCriterion'):
        return content.replace("FilterCriterion.", "FilterCriteria/") + "/" + parts_of_name[1] + '.mdo'
    if content.startswith('ChartOfCharacteristicTypes'):
        return content.replace("ChartOfCharacteristicTypes.", "ChartsOfCharacteristicTypes/") + "/" + parts_of_name[1] + '.mdo'
    return content.replace(".", "s/") + "/" + parts_of_name[1] + '.mdo'


def build_object_tree():

    obj = ObjectTree()
    path = obj.path_to_repo + obj.name_of_src
    configuration = 'src/Configuration/Configuration.mdo'
    subsystem_path = 'src/Subsystems/'

    reg_exp_pattern_subsystem = '(?<=<subsystems>Subsystem.).*?(?=</subsystems>)'
    reg_exp_pattern_content = '(?<=<content>).*?(?=</content>)'
    reg_exp_pattern_name = '(?<=<name>).*?(?=</name>)'

    # get upper subsystems
    upper_subsystems = []
    with open(path + configuration, 'r') as f:
        for line in f.readlines():
            if obj.configuration_name == '':
                m = re.search(reg_exp_pattern_name, line)
                if not (m is None):
                    obj.configuration_name = m.group()

            m = re.search(reg_exp_pattern_subsystem, line)
            if not(m is None):
                upper_subsystems.append(m.group())

    # get info about subsystems
    for subsystem in upper_subsystems:
        path_to_dir_subsystem = path + subsystem_path + subsystem + '/'
        info_subsystem = info_about_subsystems(subsystem, path_to_dir_subsystem, reg_exp_pattern_content)
        obj.subsystems.append(info_subsystem)

    return obj


def info_about_subsystems(subsystem, path, reg_exp_pattern_content):
    subsystem_name = path + subsystem + '.mdo'
    contents = []
    subsystems = []
    if os.path.isdir(path + 'Subsystems'):
        inner_subsystems = [f for f in os.listdir(path + 'Subsystems') if f != '.DS_Store']
        for inner_subsystem in inner_subsystems:
            inner_subsystem_path = path + 'Subsystems/' + inner_subsystem + '/'
            inner_info = info_about_subsystems(inner_subsystem, inner_subsystem_path, reg_exp_pattern_content)
            subsystems.append(inner_info)

    with open(subsystem_name, 'r') as f:
        for line in f.readlines():
            # contents
            m = re.search(reg_exp_pattern_content, line)
            if not (m is None):
                contents.append(m.group())

    return {subsystem: {'subsystems': subsystems, 'contents': contents}}


if __name__ == '__main__':
    obj = build_object_tree()
    # obj.print_obj()
    obj.get_commits_info()
    obj.summurize_info_to_contents()

