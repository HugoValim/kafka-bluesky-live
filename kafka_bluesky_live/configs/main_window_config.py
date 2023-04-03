from dataclasses import dataclass

@dataclass
class MainWindowConfigs:
    height: int = 800
    width: int = int(height * 16 / 9)
    title: str = "Bluesky Live View"