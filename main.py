import secret
import re
import os


class ObjectTree:
    def __init__(self, conf_name):
        self.configuration_name = conf_name
        self.subsystems = []

    def print_obj(self):
        spacer = '  '
        print(self.configuration_name)
        print(spacer + 'Подсистемы')
        count = 1
        for subsystem in self.subsystems:
            self.print_subsystem(subsystem, count, spacer)

    def print_subsystem(self, subsystem, count, spacer):
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


def build_object_tree():

    obj = ObjectTree('ДемонстрационноеПриложение')
    path = secret.path_to_configuration()
    configuration = 'src/Configuration/Configuration.mdo'
    subsystem_path = 'src/Subsystems/'

    reg_exp_pattern_subsystem = '(?<=<subsystems>Subsystem.).*?(?=</subsystems>)'
    reg_exp_pattern_content = '(?<=<content>).*?(?=</content>)'

    # get upper subsystems
    upper_subsystems = []
    with open(path + configuration, 'r') as f:
        for line in f.readlines():
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
    obj.print_obj()
