from src import codemeter, save_to_excel, save_to_markdown, settings


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
    if save_to_md:
        path = 'result/stats_info.md'
        save_to_markdown.save(structure, path)
    if save_to_xsl:
        path = 'result/stats.xlsx'
        save_to_excel.save(structure, path)
    print('')

    if save_to_md and save_to_xsl:
        print('Please check result files: stats_info.md and stats.xlsx')
    elif save_to_md:
        print('Please check result file: stats_info.md')
    elif save_to_xsl:
        print('Please check result file: stats.xlsx')
    else:
        print('Result file has not been saved. Please check settings.py - save_to_md() and save_to_xsl()')


if __name__ == '__main__':
    get_statistics()
