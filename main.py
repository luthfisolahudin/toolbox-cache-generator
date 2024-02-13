import json
import os
import pathlib
import xml.etree.ElementTree as ET
from enum import Enum


class IdeInfo:
    _channel_id: str = None

    def __init__(self, tool_id: str, folder_prefix: str):
        self.tool_id = tool_id
        self.folder_prefix = folder_prefix

    def channel_id(self):
        if self._channel_id is None:
            tool = toolbox_state(self.tool_id)

            if tool is None:
                raise RuntimeError(f'Could not get {self.tool_id} channel ID, IDE not found')

            self._channel_id = tool.get('channelId')

        return self._channel_id


class Ide(Enum):
    PHPSTORM = IdeInfo(
        tool_id='PhpStorm',
        folder_prefix='PhpStorm',
    )
    RIDER = IdeInfo(
        tool_id='Rider',
        folder_prefix='Rider',
    )
    INTELLIJ_IDEA = IdeInfo(
        tool_id='IDEA-U',
        folder_prefix='IntelliJIdea',
    )
    ANDROID_STUDIO = IdeInfo(
        tool_id='AndroidStudio',
        folder_prefix='AndroidStudio',
    )


class NewOpenItem:
    def __init__(self, tool_id: str, channel_id: str):
        self.tool_id = tool_id
        self.channel_id = channel_id

    def to_json(self):
        return {
            'toolId': self.tool_id,
            'channelId': self.channel_id,
        }


class Project:
    def __init__(self, name: str, path: str, new_open_items: list[NewOpenItem]):
        self.name = name
        self.path = path
        self.default_new_open_item = new_open_items[0].channel_id
        self.new_open_items = new_open_items

    def __str__(self):
        return f"(name: '{self.name}', path: '{self.path}', open_item: '{self.default_new_open_item}')"

    def to_json(self):
        return {
            'name': self.name,
            'path': self.path,
            'defaultNewOpenItem': self.default_new_open_item,
            'newOpenItems': [item.to_json() for item in self.new_open_items],
        }


def getenv(key: str, default: str = None) -> str:
    value = os.getenv(key, default)

    if value is None:
        raise EnvironmentError(f'Could not get environment {key}')

    return value


def toolbox_data_path(path: str | pathlib.PurePath = None) -> pathlib.PurePath:
    return pathlib.PurePath(getenv('LOCALAPPDATA'), 'JetBrains', 'Toolbox', path)


def toolbox_state(ide: str | Ide = None):
    toolbox_state_path = pathlib.Path(toolbox_data_path('state.json'))

    if not toolbox_state_path.exists():
        raise FileNotFoundError('Toolbox state file not found')

    state: dict = json.loads(toolbox_state_path.read_text())

    if ide is None:
        return state

    for tool in state.get('tools'):
        if isinstance(ide, str) and tool.get('toolId') == ide:
            return tool

        if isinstance(ide, Ide) and tool.get('toolId') == ide.value.tool_id:
            return tool

    return None


def ide_data_paths(ide: Ide) -> list[pathlib.Path]:
    folder = (
        pathlib.Path(getenv('APPDATA'), 'Google') if ide == Ide.ANDROID_STUDIO
        else pathlib.Path(getenv('APPDATA'), 'JetBrains')
    )

    if not folder.exists():
        return []

    ide_folders = folder.glob(f'{ide.value.folder_prefix}*/', case_sensitive=True)

    return list(ide_folders)


def get_recent_projects(ide: Ide, path: str | pathlib.PurePath) -> list[Project]:
    recent_projects_path = pathlib.Path(path, 'options', 'recentProjects.xml')
    recent_projects = []

    if not recent_projects_path.is_file():
        return recent_projects

    for entry in (
            ET.parse(recent_projects_path)
                    .getroot()
                    .findall('./component/[@name="RecentProjectsManager"]/option/[@name="additionalInfo"]/map/entry')
    ):
        path = pathlib.Path(entry.get('key').replace('$USER_HOME$', str(pathlib.Path.home())))

        if not path.is_dir():
            continue

        name_path = pathlib.Path(path, '.idea', '.name')

        if name_path.is_file():
            name = name_path.read_text()
        else:
            name = path.name

        recent_projects.append(
            Project(
                name=name,
                path=str(path),
                new_open_items=[NewOpenItem(tool_id=ide.value.tool_id, channel_id=ide.value.channel_id())]
            )
        )

    if ide == ide.RIDER:
        print(len(recent_projects))

    return recent_projects


def main():
    projects = []

    for ide in Ide:
        unique_project = {}

        for folder in ide_data_paths(ide):
            for project in get_recent_projects(ide, folder):
                unique_project[project.path] = project

        projects.extend(unique_project.values())

    cache_path = pathlib.Path(toolbox_data_path('cache/intellij_projects.json'))

    cache_path.write_text(json.dumps([item.to_json() for item in projects]))

    print(f'Successfully update Toolbox IntelliJ projects cache to {cache_path}')


if __name__ == '__main__':
    main()
