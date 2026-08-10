from sports_data_layer.adapters.generic_mapping_adapter import GenericMappingAdapter
from sports_data_layer.analysis_service import run_hypotheses
from sports_data_layer.capabilities import Capability, CapabilityMatrix

matrix = CapabilityMatrix()
matrix.set('fake', {Capability.BASIC_RESULTS})
adapter = GenericMappingAdapter('fake', 'https://example.invalid', matrix, mapping={'competition': 'competition', 'league_id': '1'})
payloads = [
    {'events': [
        {'idEvent': 'a', 'dateEvent': '2025-01-01', 'idHomeTeam': '1', 'strHomeTeam': 'A', 'idAwayTeam': '2', 'strAwayTeam': 'B', 'intHomeScore': '2', 'intAwayScore': '0'},
        {'idEvent': 'b', 'dateEvent': '2025-01-08', 'idHomeTeam': '2', 'strHomeTeam': 'B', 'idAwayTeam': '1', 'strAwayTeam': 'A', 'intHomeScore': '1', 'intAwayScore': '1'},
    ]},
    {'events': [
        {'idEvent': 'b', 'dateEvent': '2025-01-08', 'idHomeTeam': '2', 'strHomeTeam': 'B', 'idAwayTeam': '1', 'strAwayTeam': 'A', 'intHomeScore': '1', 'intAwayScore': '1'},
        {'idEvent': 'c', 'dateEvent': '2025-01-15', 'idHomeTeam': '1', 'strHomeTeam': 'A', 'idAwayTeam': '2', 'strAwayTeam': 'B', 'intHomeScore': '3', 'intAwayScore': '0'},
    ]},
]
adapter._request_json = lambda url=None: payloads.pop(0)
matches = adapter.get_matches_by_rounds([1, 2], '2025')
assert [match.id for match in matches] == ['a', 'b', 'c']
discoveries = run_hypotheses(matches, [])
print('unique_matches=', len(matches), 'discoveries=', len(discoveries))
