from src import codemeter, save_to_excel, save_to_markdown, save_to_html, settings


def get_statistics():
    structure = codemeter.StructureOfCodemeter()
    structure.collect_data()
    if structure is None:
        return

    if len(structure.structure_of_conf) == 0:
        print('Nothing was found. Check the settings')
        print('For example: settings.date_since() and settings.date_before()')
        return

    print('Statistics are collected!')
    save_to_md = settings.save_to_md()
    save_to_xsl = settings.save_to_xsl()
    save_to_web = settings.save_to_html()
    if save_to_md:
        path_to_md = 'result/stats.md'
        save_to_markdown.save(structure, path_to_md)
    if save_to_xsl:
        path_to_xls = 'result/stats.xlsx'
        save_to_excel.save(structure, path_to_xls)
    if save_to_web:
        path_to_web = 'result/stats.html'
        save_to_html.save(structure, path_to_web)
    print('')

    if not(save_to_md or save_to_xsl or save_to_web):
        print('Result file has not been saved. Please check settings.py')
    else:
        print('Please check result files:')
        if save_to_md:
            print(path_to_md)
        if save_to_xsl:
            print(path_to_xls)
        if save_to_web:
            print(path_to_web)


if __name__ == '__main__':
    get_statistics()
