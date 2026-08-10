from datetime import date, timedelta

from sports_data_layer.models import Match, TeamRef
from sports_data_layer.temporal_analysis import build_prematch_snapshots, split_chronologically, run_temporal_analysis

A = TeamRef('a', 'A')
B = TeamRef('b', 'B')
C = TeamRef('c', 'C')
D = TeamRef('d', 'D')
matches = []
for i in range(20):
    home, away = ((A, B) if i % 2 == 0 else (C, D))
    matches.append(Match(str(i), date(2025, 1, 1) + timedelta(days=i), home, away, 2 if i % 3 else 0, 0 if i % 3 else 1, 'competition', '2025'))
train, future = split_chronologically(matches, 0.65)
assert train[-1].date < future[0].date
snapshots = build_prematch_snapshots(matches)
assert snapshots[0].prior_matches == 0
assert any(snapshot.prior_matches >= 1 for snapshot in snapshots)
evidence, snapshots_again = run_temporal_analysis(matches, discovery_fraction=0.65)
assert len(snapshots_again) == len(snapshots)
print('train=', len(train), 'future=', len(future), 'snapshots=', len(snapshots_again), 'evidence=', len(evidence))
