import datetime

import secret
import re
import os
import git
import copy
from tqdm import tqdm


class ObjectTree:
    def __init__(self):
        self.path_to_repo = secret.path_to_repo()
        self.name_of_src = secret.name_of_configuration()
        self.date_since = datetime.datetime(2016, 1, 1)
        self.configuration_name = ''
        self.subsystems = []
        self.commits = []
        self.summarized_info = {}
        self.structure = {}
        self.authors = {}

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
                print(spacer * (count + 1) + single_to_plural(content).replace('.', '/'))

    def get_commits_info(self):
        repo = git.Repo(self.path_to_repo)
        commits = list(repo.iter_commits("master"))
        with tqdm(total=len(commits), desc='Get commits', ncols=100, colour='green') as pbar:
            for commit in commits:
                pbar.update(1)
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
                        self.commits.append(stat)
                        self.authors[commit.author.email] = commit.author.name

    def summarize_info_to_contents(self):
        summarized = {}
        if len(self.commits) == 0:
            return
        for commit in self.commits:
            file = commit.get('file')
            email = commit.get('email')
            file_info = summarized.get(file)
            if file_info is None:
                file_info = {email: {'insert': 0, 'delete': 0}}
            email_info = file_info.get(email)
            if email_info is None:
                email_info = {'insert': 0, 'delete': 0}
            email_info.update({'insert': email_info.get('insert') + commit.get('insert')})
            email_info.update({'delete': email_info.get('delete') + commit.get('delete')})
            file_info.update({email: email_info})
            summarized.update({file: file_info})

        self.summarized_info = summarized

    def sort_by_content_and_subsystem(self):
        structure = {}
        for file in self.summarized_info:
            email_info = self.summarized_info.get(file)
            # example: DemoConfDT/src/AccumulationRegisters/Взаиморасчеты/Forms/ТекущиеВзаиморасчеты/Module.bsl
            file = file.replace(secret.name_of_configuration() + 'src/', '')
            parts_of_name = file.split('/')
            type = parts_of_name[0]  # example: AccumulationRegisters
            object = parts_of_name[1]  # example: Взаиморасчеты
            type_info = copy.deepcopy(structure.get(type, {}))
            object_info = copy.deepcopy(type_info.get(object, {}))
            info = object_info
            for i in range(2, len(parts_of_name)):
                inner_info = info.get(parts_of_name[i])
                if inner_info is None:
                    info.update({parts_of_name[i]: {}})
                    inner_info = info.get(parts_of_name[i])
                info = inner_info
                if i == len(parts_of_name) - 1:
                    info.update(email_info)
            type_info.update({object: object_info})

            # stats by type
            for email_info_by_author in email_info:
                authors = copy.deepcopy(type_info.get('authors', {}))
                author = authors.get(email_info_by_author)
                if author is None:
                    author = copy.deepcopy(email_info.get(email_info_by_author, {}))
                else:
                    author.update({'insert': author.get('insert', 0) + email_info.get(
                                                                  email_info_by_author).get('insert', 0)})
                    author.update({'delete': author.get('delete', 0) + email_info.get(
                                                                  email_info_by_author).get('delete', 0)})
                authors[email_info_by_author] = author
                type_info['authors'] = authors
            structure.update({type: type_info})

            # common info about stats
            for email_info_by_author in email_info:
                structure_authors = structure.get('authors', {})
                structure_author = structure_authors.get(email_info_by_author)
                if structure_author is None:
                    structure_author = email_info.get(email_info_by_author)
                else:
                    structure_author.update({'insert': structure_author.get('insert', 0) + email_info.get(
                        email_info_by_author).get('insert', 0)})
                    structure_author.update({'delete': structure_author.get('delete', 0) + email_info.get(
                        email_info_by_author).get('delete', 0)})
                structure_authors.update({email_info_by_author: structure_author})
                structure.update({'authors': structure_authors})
        self.structure = structure
        return

    def print_structure(self):

        if len(self.structure) == 0:
            return

        with open('stats_info.md', 'w') as result_file:
            write_line(result_file, self.configuration_name, '#')
            write_line(result_file, 'Авторы:', '##')
            print_authors(self.authors, self.structure.get('authors'), result_file)

            write_line(result_file, 'Объекты:', '##')
            for obj in self.structure:
                if obj == 'authors':
                    continue
                else:
                    write_line(result_file, obj, '###')
                    types = self.structure.get(obj)
                    for type in types:
                        if type == 'authors':
                            continue
                        else:
                            write_line(result_file, type, '####')
                            if obj == 'CommonModules':
                                lines_info = types.get(type).get('Module.bsl')
                                print_authors(self.authors, lines_info, result_file)
                            elif obj == 'Catalogs':
                                catalog_info = types.get(type)
                                if catalog_info.get('ObjectModule.bsl') is not None:
                                    write_line(result_file, '', '')
                                    write_line(result_file, '**Модуль объекта**', '')
                                    write_line(result_file, '', '')
                                    lines_info = catalog_info.get('ObjectModule.bsl')
                                    print_authors(self.authors, lines_info, result_file)

                                if catalog_info.get('ManagerModule.bsl') is not None:
                                    write_line(result_file, '', '')
                                    write_line(result_file, '**Модуль менеджера**', '')
                                    write_line(result_file, '', '')
                                    lines_info = catalog_info.get('ManagerModule.bsl')
                                    print_authors(self.authors, lines_info, result_file)

                                if catalog_info.get('Forms') is not None:
                                    write_line(result_file, '', '')
                                    write_line(result_file, '**Формы**', '')
                                    write_line(result_file, '', '')
                                    forms_info = catalog_info.get('Forms')
                                    for form in forms_info:
                                        write_line(result_file, '', '')
                                        write_line(result_file, form, '')
                                        write_line(result_file, '', '')
                                        lines_info = forms_info.get(form).get('Module.bsl')
                                        print_authors(self.authors, lines_info, result_file)


def print_authors(authors, lines_info, file):
    number = 1
    for author in lines_info:
        author_info = lines_info.get(author)
        write_line(file, '{num}. {name} <{email}> {insert} {delete}'.format(
            num=number,
            name=authors.get(author),
            email=author,
            insert=color_text('+ {}'.format(author_info.get('insert', 0)), 'green'),
            delete=color_text('- {}'.format(author_info.get('delete', 0)), 'red')))
        number += 1


def color_text(text, color):
    return '<span style="color:{color}">{text}</span>'.format(color=color, text=text)


def write_line(file, content, tag=''):
    if tag == '':
        file.write(content)
    else:
        file.write('{tag} {content}'.format(tag=tag, content=content))
    file.write('\n')


def single_to_plural(content):
    if content.startswith('FilterCriterion'):
        return content.replace("FilterCriterion", "FilterCriteria")
    if content.startswith('ChartOfCharacteristicTypes'):
        return content.replace("ChartOfCharacteristicTypes", "ChartsOfCharacteristicTypes")
    else:
        return content.replace(".", "s.")


def path_to_object(content):
    content = single_to_plural(content)
    parts_of_name = content.split('.')
    return content.replace(".", "/") + "/" + parts_of_name[1] + '.mdo'


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
            if not (m is None):
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
    obj.summarize_info_to_contents()
    obj.sort_by_content_and_subsystem()
    obj.print_structure()
