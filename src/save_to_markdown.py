from tqdm import tqdm


def color_text(text, color):
    return '<span style="color:{color}">{text}</span>'.format(color=color, text=text)


def write_line(file, content, tag=''):
    if tag == '':
        file.write(content)
    else:
        if '#' in tag:
            # Headings should be surrounded by blank lines
            file.write('\n')
        file.write('{tag} {content}'.format(tag=tag, content=content))
        if '#' in tag:
            file.write('\n')
    file.write('\n')


def open_details(title, file):
    write_line(file, '<details>', '')
    write_line(file, '  <summary><i>{title}</i></summary>'.format(title=title), '')
    write_line(file, '', '')


def close_details(file):
    write_line(file, '</details>', '')
    write_line(file, '', '')


def write_title(title, file):
    write_line(file, title, '')
    write_line(file, '', '')


def icon_md(name):
    return '<img title="{name}" align=center width=16 height=16 src="../src/icons/{name}.png"> '.format(name=name)


def print_authors(authors, lines_info, file):

    if lines_info is None or len(lines_info) == 0:
        return

    new_lines_info = {}
    for author in lines_info:
        name = '{name} <{email}>'.format(name=authors.get(author), email=author)
        new_lines_info[name] = lines_info.get(author)

    sorted_lines_info = dict(sorted(new_lines_info.items()))

    number = 1
    for author in sorted_lines_info:
        author_info = sorted_lines_info.get(author)
        write_line(file, '{num}. {name} {insert} {delete}'.format(
            num=number,
            name=author,
            insert=color_text('+{}'.format(author_info.get('insert', 0)), 'rgb(0,128,0)'),
            delete=color_text('-{}'.format(author_info.get('delete', 0)), 'rgb(255,0,0)')))
        number += 1
    write_line(file, '')


def print_subsystem(subsystems, file):
    if len(subsystems) > 0:
        subsystems = sorted(subsystems)
        write_line(file, "##### Подсистемы")
        write_line(file, '')
        for subsystem in subsystems:
            write_line(file, subsystem, '-')
        write_line(file, '')


def save(conf, path='result/stats_info.md'):
    if len(conf.structure_of_conf) == 0:
        return

    with tqdm(total=len(conf.structure_of_conf), desc='Save to markdown', ncols=100, colour='green') as pbar:
        with open(path, 'w', encoding='utf-8') as result_file:
            write_line(result_file, conf.configuration_name, '#')
            open_details('Отборы:', result_file)
            if conf.date_since is not None \
                    and conf.date_before is not None:
                write_line(result_file, 'Коммиты собраны начиная с {since} по {before}'.format(
                    since=conf.date_since.date(), before=conf.date_before.date()))
                write_line(result_file, '')
            elif conf.date_since is not None:
                write_line(result_file, 'Коммиты собраны начиная с {since}'.format(since=conf.date_since.date()))
                write_line(result_file, '')
            elif conf.date_before is not None:
                write_line(result_file, 'Коммиты собраны по {before}'.format(before=conf.date_before.date()))
                write_line(result_file, '')
            if len(conf.include_subsystems) > 0:
                write_line(result_file, 'Отбор по этим подсистемам:')
                for subsystem in conf.include_subsystems:
                    write_line(result_file, subsystem, '-')
                write_line(result_file, '')
            if len(conf.exclude_subsystems) > 0:
                write_line(result_file, 'Исключая эти подсистемы:')
                for subsystem in conf.exclude_subsystems:
                    write_line(result_file, subsystem, '-')
                write_line(result_file, '')
            close_details(result_file)

            write_line(result_file, 'Разработчики:', '##')
            print_authors(conf.authors, conf.structure_of_conf.get('authors'), result_file)

            write_line(result_file, 'Объекты:', '##')
            for object_name in conf.structure_of_conf:
                pbar.update(1)
                if object_name == 'authors' or object_name == 'Configuration':
                    continue
                else:
                    subsystem_obj = conf.subsystem_by_object.get(object_name, {})
                    write_line(result_file, icon_md(object_name) + object_name, '###')
                    open_details('Подробнее', result_file)
                    types = conf.structure_of_conf.get(object_name)
                    for type_name in types:
                        if type_name == 'authors':
                            continue
                        else:
                            write_line(result_file, icon_md(object_name) + type_name, '####')
                            object_info = types.get(type_name)
                            print_authors(conf.authors, object_info.get('authors'), result_file)
                            subsystem_type = subsystem_obj.get(type_name, [])
                            print_subsystem(subsystem_type, result_file)
                            if object_name == 'Catalogs' or object_name == 'DataProcessors' \
                                    or object_name == 'Documents' or object_name == 'Reports':
                                open_details('Еще', result_file)
                                if object_info.get('ObjectModule.bsl') is not None:
                                    write_title('##### Модуль объекта', result_file)
                                    lines_info = object_info.get('ObjectModule.bsl')
                                    print_authors(conf.authors, lines_info, result_file)

                                if object_info.get('ManagerModule.bsl') is not None:
                                    write_title('##### Модуль менеджера', result_file)
                                    lines_info = object_info.get('ManagerModule.bsl')
                                    print_authors(conf.authors, lines_info, result_file)

                                if object_info.get('Forms') is not None:
                                    write_title('##### Формы', result_file)
                                    forms_info = object_info.get('Forms')
                                    for form in forms_info:
                                        write_title(form, result_file)
                                        lines_info = forms_info.get(form).get('Module.bsl')
                                        print_authors(conf.authors, lines_info, result_file)
                                close_details(result_file)

                            elif object_name == 'InformationRegisters' or object_name == 'AccumulationRegisters':
                                open_details('Еще', result_file)
                                if object_info.get('RecordSetModule.bsl') is not None:
                                    write_title('##### Модуль записи', result_file)
                                    lines_info = object_info.get('RecordSetModule.bsl')
                                    print_authors(conf.authors, lines_info, result_file)
                                if object_info.get('Forms') is not None:
                                    write_title('##### Формы', result_file)
                                    forms_info = object_info.get('Forms')
                                    for form in forms_info:
                                        write_title(form, result_file)
                                        lines_info = forms_info.get(form).get('Module.bsl')
                                        print_authors(conf.authors, lines_info, result_file)
                                close_details(result_file)

                    close_details(result_file)
