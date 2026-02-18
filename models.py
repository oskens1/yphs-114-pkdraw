import math

class EloManager:
    K = 32

    @staticmethod
    def calculate_expected_score(elo_a, elo_b):
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    @classmethod
    def update_elo(cls, elo_a, elo_b, winner):
        """
        winner: 'A' or 'B'
        """
        expected_a = cls.calculate_expected_score(elo_a, elo_b)
        expected_b = cls.calculate_expected_score(elo_b, elo_a)

        score_a = 1 if winner == 'A' else 0
        score_b = 1 if winner == 'B' else 0

        # 計算變化量
        change_a = cls.K * (score_a - expected_a)
        change_b = cls.K * (score_b - expected_b)
        
        # 強制確保至少有 1 分的變動，增加視覺回饋感
        if change_a > 0 and change_a < 1: change_a = 1
        if change_a < 0 and change_a > -1: change_a = -1
        if change_b > 0 and change_b < 1: change_b = 1
        if change_b < 0 and change_b > -1: change_b = -1

        new_elo_a = elo_a + change_a
        new_elo_b = elo_b + change_b

        return round(new_elo_a), round(new_elo_b)

class WorkItem:
    def __init__(self, id, image_url, elo=1500, match_count=0, win_count=0, team="red"):
        self.id = id
        self.image_url = image_url
        self.elo = elo
        self.match_count = match_count
        self.win_count = win_count
        self.team = team

    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "elo": self.elo,
            "match_count": self.match_count,
            "win_count": self.win_count,
            "team": self.team
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
