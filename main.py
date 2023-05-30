import secret


class ObjectTree:
    def __init__(self, conf_name):
        self.configuration_name = conf_name
        self.subsystems = []


def build_object_tree():
    path = secret.path_to_configuration()
    configuration = 'src/Configuration/Configuration.mdo'
    conf_file = path + configuration

    with open(conf_file, 'r') as f:
        print(f.readlines())

    obj = ObjectTree('ДемонстрационноеПриложение')
    print(obj.configuration_name)



if __name__ == '__main__':
    build_object_tree()
