from pydantic import BaseModel

class SUser(BaseModel):
    id: int | None = None
    username: str | None = None
    player_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None


class SAnalysis(BaseModel):
    mistake_total: int | None = None
    mistake_doubling: int | None = None
    mistake_taking: int | None = None
    luck: float | None = None 
    pr: float | None = None 
    user_id: int
    file_name: str | None = None
    file_path: str | None = None
    game_id: str | None = None


class SDetailedAnalysis(BaseModel):
    # Player info
    user_id: int
    player_name: str
    
    # Chequerplay
    moves_marked_bad: int
    moves_marked_very_bad: int
    error_rate_chequer: float
    chequerplay_rating: str

    # Luck
    rolls_marked_very_lucky: int
    rolls_marked_lucky: int
    rolls_marked_unlucky: int
    rolls_marked_very_unlucky: int
    rolls_rate_chequer: float
    luck_rating: str

    # Cube
    cube_decision_rating: str

    # Overall
    snowie_error_rate: float
    overall_rating: str

    # File info
    file_name: str | None = None
    file_path: str | None = None
    game_id: str | None = None

    class Config:
        from_attributes = True