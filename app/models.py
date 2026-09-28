from pydantic import BaseModel


class AnalyzeResult(BaseModel):
    title: str | None = None
    author: str | None = None
    source_url: str
    summary: str
    people_and_scene: str
    actions: str
    spoken_content: str
    on_screen_text: str
    event_flow: list[str]
    one_line_summary: str
    transcript: str = ""
    frame_count: int = 0
