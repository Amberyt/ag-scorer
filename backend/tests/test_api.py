import uuid
from fastapi.testclient import TestClient
from app.main import app


def test_auth_team_match_scoring_and_undo():
    email = f"tester-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        response = client.post('/auth/register', json={
            'name': 'Test Scorer', 'email': email, 'password': 'test-pass-123'
        })
        assert response.status_code == 200
        token = response.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        teams = []
        for name, code in [('Test XI A', 'TXA'), ('Test XI B', 'TXB')]:
            r = client.post('/teams', headers=headers, json={'name': name, 'short_name': code})
            assert r.status_code == 201
            teams.append(r.json()['id'])

        player_ids = []
        for team_id, prefix in [(teams[0], 'A'), (teams[1], 'B')]:
            created = []
            for i in range(3):
                p = client.post(f'/teams/{team_id}/players', headers=headers,
                                json={'name': f'{prefix} Player {i+1}', 'role': 'All-rounder', 'jersey_number': i+1})
                assert p.status_code == 201
                created.append(p.json()['id'])
            player_ids.append(created)

        match_response = client.post('/matches', headers=headers, json={
            'title': 'Test XI A vs Test XI B', 'venue': 'Test Ground', 'match_format': 'T10',
            'total_overs': 1, 'team_a_id': teams[0], 'team_b_id': teams[1],
            'toss_winner_id': teams[0], 'toss_decision': 'bat',
            'striker_id': player_ids[0][0], 'non_striker_id': player_ids[0][1],
            'bowler_id': player_ids[1][0],
        })
        assert match_response.status_code == 201, match_response.text
        match_id = match_response.json()['id']

        ball = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 4})
        assert ball.status_code == 201, ball.text
        assert ball.json()['score']['runs'] == 4
        assert ball.json()['score']['legal_balls'] == 1

        wide = client.post(f'/matches/{match_id}/balls', headers=headers, json={
            'extra_type': 'wide', 'extra_runs': 2, 'running_runs': 1,
        })
        assert wide.status_code == 201, wide.text
        assert wide.json()['score']['runs'] == 6
        assert wide.json()['score']['legal_balls'] == 1

        undo = client.post(f'/matches/{match_id}/undo', headers=headers)
        assert undo.status_code == 200, undo.text
        assert undo.json()['score']['runs'] == 4
        assert undo.json()['score']['legal_balls'] == 1

        stats = client.get(f"/players/{player_ids[0][0]}/stats", headers=headers)
        assert stats.status_code == 200
        assert stats.json()['runs'] == 4


def test_two_innings_chase_completes_match():
    email = f"chase-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        response = client.post('/auth/register', json={
            'name': 'Chase Tester', 'email': email, 'password': 'test-pass-123'
        })
        assert response.status_code == 200
        headers = {'Authorization': f"Bearer {response.json()['access_token']}"}
        team_ids, player_ids = [], []
        for suffix in ('A', 'B'):
            team = client.post('/teams', headers=headers, json={'name': f'Chase {suffix}', 'short_name': f'C{suffix}'})
            assert team.status_code == 201
            team_ids.append(team.json()['id'])
            players = []
            for i in range(3):
                player = client.post(f"/teams/{team.json()['id']}/players", headers=headers,
                                     json={'name': f'{suffix} Batter {i+1}', 'role': 'All-rounder'})
                assert player.status_code == 201
                players.append(player.json()['id'])
            player_ids.append(players)
        match = client.post('/matches', headers=headers, json={
            'title': 'Chase match', 'team_a_id': team_ids[0], 'team_b_id': team_ids[1],
            'toss_winner_id': team_ids[0], 'toss_decision': 'bat', 'total_overs': 1,
            'striker_id': player_ids[0][0], 'non_striker_id': player_ids[0][1], 'bowler_id': player_ids[1][0],
        })
        assert match.status_code == 201, match.text
        match_id = match.json()['id']
        for _ in range(6):
            ball = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 1})
            assert ball.status_code == 201, ball.text
        assert ball.json()['status'] == 'innings_break'
        started = client.post(f'/matches/{match_id}/next-innings', headers=headers, json={
            'striker_id': player_ids[1][0], 'non_striker_id': player_ids[1][1], 'bowler_id': player_ids[0][0],
        })
        assert started.status_code == 200, started.text
        six = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 6})
        assert six.status_code == 201
        assert six.json()['status'] == 'live'
        one = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 1})
        assert one.status_code == 201, one.text
        assert one.json()['status'] == 'completed'
        assert one.json()['winner_id'] == team_ids[1]


def test_common_player_can_be_selected_for_either_team_with_one_identity():
    email = f"shared-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        response = client.post('/auth/register', json={
            'name': 'Shared Player Tester', 'email': email, 'password': 'test-pass-123'
        })
        assert response.status_code == 200
        headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

        team_ids, rosters = [], []
        for suffix in ('A', 'B'):
            team = client.post('/teams', headers=headers, json={
                'name': f'Shared {suffix}', 'short_name': f'S{suffix}'
            })
            assert team.status_code == 201
            team_ids.append(team.json()['id'])
            roster = []
            for index in range(2):
                player = client.post(f"/teams/{team.json()['id']}/players", headers=headers, json={
                    'name': f'{suffix} Player {index + 1}', 'role': 'All-rounder'
                })
                assert player.status_code == 201
                roster.append(player.json()['id'])
            rosters.append(roster)

        common = client.post('/players/common', headers=headers, json={
            'home_team_id': team_ids[0], 'name': 'Sam Shared', 'role': 'All-rounder', 'jersey_number': 99
        })
        assert common.status_code == 201, common.text
        shared_id = common.json()['id']

        team_b_players = client.get(f'/teams/{team_ids[1]}/players', headers=headers)
        assert team_b_players.status_code == 200
        assert any(p['id'] == shared_id and p['is_common'] for p in team_b_players.json())

        match = client.post('/matches', headers=headers, json={
            'title': 'Shared player match', 'team_a_id': team_ids[0], 'team_b_id': team_ids[1],
            'toss_winner_id': team_ids[0], 'toss_decision': 'bat', 'total_overs': 1,
            'striker_id': rosters[0][0], 'non_striker_id': rosters[0][1], 'bowler_id': shared_id,
        })
        assert match.status_code == 201, match.text
        match_id = match.json()['id']

        for _ in range(6):
            ball = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 1})
            assert ball.status_code == 201, ball.text
        assert ball.json()['status'] == 'innings_break'

        next_innings = client.post(f'/matches/{match_id}/next-innings', headers=headers, json={
            'striker_id': shared_id, 'non_striker_id': rosters[1][0], 'bowler_id': rosters[0][0]
        })
        assert next_innings.status_code == 200, next_innings.text
        scored = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 2})
        assert scored.status_code == 201, scored.text
        assert scored.json()['striker']['id'] == shared_id  # two runs leave the shared player on strike

        stats = client.get(f'/players/{shared_id}/stats', headers=headers)
        assert stats.status_code == 200
        assert stats.json()['is_common'] is True
        assert stats.json()['runs'] == 2
        assert stats.json()['bowling_overs'] == '1.0'



def test_single_batter_mode_has_no_non_striker_and_does_not_rotate_strike():
    email = f"solo-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        response = client.post('/auth/register', json={
            'name': 'Solo Tester', 'email': email, 'password': 'test-pass-123'
        })
        assert response.status_code == 200
        headers = {'Authorization': f"Bearer {response.json()['access_token']}"}
        teams, rosters = [], []
        for suffix in ('A', 'B'):
            team = client.post('/teams', headers=headers, json={'name': f'Solo {suffix}', 'short_name': f'S{suffix}'})
            assert team.status_code == 201
            teams.append(team.json()['id'])
            roster = []
            for index in range(3):
                player = client.post(f"/teams/{team.json()['id']}/players", headers=headers, json={
                    'name': f'{suffix} Solo Player {index + 1}', 'role': 'All-rounder'
                })
                assert player.status_code == 201
                roster.append(player.json()['id'])
            rosters.append(roster)

        created = client.post('/matches', headers=headers, json={
            'title': 'Solo format', 'team_a_id': teams[0], 'team_b_id': teams[1],
            'toss_winner_id': teams[0], 'toss_decision': 'bat', 'total_overs': 1,
            'striker_id': rosters[0][0], 'bowler_id': rosters[1][0], 'single_batter_mode': True,
        })
        assert created.status_code == 201, created.text
        match_id = created.json()['id']
        assert created.json()['single_batter_mode'] is True
        assert created.json()['non_striker'] is None

        one = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 1})
        assert one.status_code == 201, one.text
        assert one.json()['striker']['id'] == rosters[0][0]  # odd runs do not rotate in solo mode
        assert one.json()['non_striker'] is None

        wicket = client.post(f'/matches/{match_id}/balls', headers=headers, json={
            'wicket_type': 'bowled', 'dismissed_player_id': rosters[0][0], 'new_batter_id': rosters[0][1]
        })
        assert wicket.status_code == 201, wicket.text
        assert wicket.json()['striker']['id'] == rosters[0][1]
        assert wicket.json()['non_striker'] is None

        undone = client.post(f'/matches/{match_id}/undo', headers=headers)
        assert undone.status_code == 200, undone.text
        assert undone.json()['striker']['id'] == rosters[0][0]
        assert undone.json()['non_striker'] is None
        assert undone.json()['score']['runs'] == 1

        # Complete the first over: solo mode must retain the same striker.
        for _ in range(5):
            ball = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 0})
            assert ball.status_code == 201, ball.text
        assert ball.json()['status'] == 'innings_break'
        assert ball.json()['striker']['id'] == rosters[0][0]
        assert ball.json()['non_striker'] is None

        second = client.post(f'/matches/{match_id}/next-innings', headers=headers, json={
            'striker_id': rosters[1][0], 'bowler_id': rosters[0][0]
        })
        assert second.status_code == 200, second.text
        assert second.json()['single_batter_mode'] is True
        assert second.json()['non_striker'] is None


def test_same_shared_player_identity_can_bat_for_both_teams_in_one_match():
    email = f"shared-both-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        response = client.post('/auth/register', json={
            'name': 'Shared Both Sides Tester', 'email': email, 'password': 'test-pass-123'
        })
        assert response.status_code == 200
        headers = {'Authorization': f"Bearer {response.json()['access_token']}"}
        team_ids, players = [], []
        for suffix in ('A', 'B'):
            team = client.post('/teams', headers=headers, json={'name': f'Both {suffix}', 'short_name': f'B{suffix}'})
            assert team.status_code == 201
            team_ids.append(team.json()['id'])
            roster = []
            for index in range(2):
                player = client.post(f"/teams/{team.json()['id']}/players", headers=headers, json={
                    'name': f'{suffix} Regular {index + 1}', 'role': 'All-rounder'
                })
                assert player.status_code == 201
                roster.append(player.json()['id'])
            players.append(roster)

        common = client.post('/players/common', headers=headers, json={
            'home_team_id': team_ids[0], 'name': 'Shared Across Both Sides', 'role': 'All-rounder'
        })
        assert common.status_code == 201, common.text
        shared_id = common.json()['id']

        # Team A selects the shared profile as its opening batter.
        created = client.post('/matches', headers=headers, json={
            'title': 'Shared player on both sides', 'team_a_id': team_ids[0], 'team_b_id': team_ids[1],
            'toss_winner_id': team_ids[0], 'toss_decision': 'bat', 'total_overs': 1,
            'striker_id': shared_id, 'non_striker_id': players[0][0], 'bowler_id': players[1][0],
        })
        assert created.status_code == 201, created.text
        match_id = created.json()['id']
        assert created.json()['striker']['id'] == shared_id

        first_ball = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 2})
        assert first_ball.status_code == 201, first_ball.text
        for _ in range(5):
            ball = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 0})
            assert ball.status_code == 201, ball.text
        assert ball.json()['status'] == 'innings_break'

        # The same player ID is selectable from Team B's roster for the chase.
        second = client.post(f'/matches/{match_id}/next-innings', headers=headers, json={
            'striker_id': shared_id, 'non_striker_id': players[1][0], 'bowler_id': players[0][0]
        })
        assert second.status_code == 200, second.text
        assert second.json()['striker']['id'] == shared_id

        scored = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 3})
        assert scored.status_code == 201, scored.text
        stats = client.get(f'/players/{shared_id}/stats', headers=headers)
        assert stats.status_code == 200
        assert stats.json()['runs'] == 5  # same player profile totals both team appearances
        assert stats.json()['is_common'] is True



def test_pwa_shell_assets_are_served():
    with TestClient(app) as client:
        manifest = client.get('/manifest.webmanifest')
        assert manifest.status_code == 200
        assert manifest.json()['display'] == 'standalone'
        assert client.get('/sw.js').status_code == 200
        assert client.get('/icons/icon-192.png').status_code == 200
        assert client.get('/icons/icon-512.png').status_code == 200


def test_mvp_rankings_include_batting_and_bowler_credited_wickets():
    email = f"mvp-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        response = client.post('/auth/register', json={
            'name': 'MVP Tester', 'email': email, 'password': 'test-pass-123'
        })
        assert response.status_code == 200
        headers = {'Authorization': f"Bearer {response.json()['access_token']}"}

        teams, players = [], []
        for suffix in ('A', 'B'):
            team = client.post('/teams', headers=headers, json={
                'name': f'MVP {suffix}', 'short_name': f'M{suffix}'
            })
            assert team.status_code == 201
            teams.append(team.json()['id'])
            roster = []
            for index in range(3):
                player = client.post(f"/teams/{team.json()['id']}/players", headers=headers, json={
                    'name': f'{suffix} MVP Player {index + 1}', 'role': 'All-rounder'
                })
                assert player.status_code == 201
                roster.append(player.json()['id'])
            players.append(roster)

        match = client.post('/matches', headers=headers, json={
            'title': 'MVP ranking match', 'team_a_id': teams[0], 'team_b_id': teams[1],
            'toss_winner_id': teams[0], 'toss_decision': 'bat', 'total_overs': 2,
            'striker_id': players[0][0], 'non_striker_id': players[0][1],
            'bowler_id': players[1][0],
        })
        assert match.status_code == 201, match.text
        match_id = match.json()['id']

        four = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 4})
        assert four.status_code == 201, four.text
        six = client.post(f'/matches/{match_id}/balls', headers=headers, json={'runs_bat': 6})
        assert six.status_code == 201, six.text
        wicket = client.post(f'/matches/{match_id}/balls', headers=headers, json={
            'wicket_type': 'bowled', 'dismissed_player_id': players[0][0],
            'new_batter_id': players[0][2],
        })
        assert wicket.status_code == 201, wicket.text

        match_rankings = client.get(f'/matches/{match_id}/mvp', headers=headers)
        assert match_rankings.status_code == 200, match_rankings.text
        rows = match_rankings.json()['rankings']
        by_id = {row['player_id']: row for row in rows}
        assert rows[0]['player_id'] == players[1][0]
        assert by_id[players[1][0]]['wickets'] == 1
        assert by_id[players[1][0]]['points'] == 20
        assert by_id[players[0][0]]['runs'] == 10
        assert by_id[players[0][0]]['points'] == 13

        overall = client.get('/mvp-rankings', headers=headers)
        assert overall.status_code == 200, overall.text
        assert overall.json()['rankings'][0]['player_id'] == players[1][0]
        assert '1 point per run' in overall.json()['points_formula']
