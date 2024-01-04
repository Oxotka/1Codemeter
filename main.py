import secret
import re


class ObjectTree:
    def __init__(self, conf_name):
        self.configuration_name = conf_name
        self.subsystems = []


def build_object_tree():

    obj = ObjectTree('ДемонстрационноеПриложение')
    print(obj.configuration_name)

    path = secret.path_to_configuration()
    configuration = 'src/Configuration/Configuration.mdo'
    subsystem_path = 'src/Subsystems/'

    conf_file = path + configuration

    reg_exp_pattern_subsystem = '(?<=<subsystems>Subsystem.).*?(?=</subsystems>)'
    reg_exp_pattern_content = '(?<=<content>).*?(?=</content>)'

    # get upper subsystems
    upper_subsystems = []
    with open(conf_file, 'r') as f:
        for line in f.readlines():
            m = re.search(reg_exp_pattern_subsystem, line)
            if not(m is None):
                upper_subsystems.append(m.group())

    for subsystem in upper_subsystems:
        contents = []
        subsystems = []
        subsystem_name = path + subsystem_path + subsystem + '/' + subsystem + '.mdo'
        with open(subsystem_name, 'r') as f:
            for line in f.readlines():
                m = re.search(reg_exp_pattern_subsystem, line)
                if not (m is None):
                    subsystems.append(m.group())

                m = re.search(reg_exp_pattern_content, line)
                if not (m is None):
                    contents.append(m.group())
        info = {'subsystems': subsystems, 'contents': contents}
        obj.subsystems.append({subsystem: info})

    print(obj.subsystems)


if __name__ == '__main__':
    build_object_tree()
