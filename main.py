import secret


def build_object_tree():
    path = secret.path_to_configuration()
    print(path)


if __name__ == '__main__':
    build_object_tree()
