"""Usage: python request_experiment.py topology.json parameters.json. Input times are seconds."""
import json
import sys
from math import isfinite
from pathlib import Path
from sequence.constants import SECOND, BARRET_KOK
from sequence.topology.router_net_topo import RouterNetTopo
from sequence.app.request_app import RequestApp
from sequence.entanglement_management.generation import EntanglementGenerationA, EntanglementGenerationB
from sequence.kernel.event import Event
from sequence.kernel.process import Process

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
parameters = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
stop = float(parameters['stop_time_s'])
if not isfinite(stop) or stop * SECOND < 1:
    raise ValueError('stop_time_s must be finite and at least 1 ps.')
config['stop_time'] = int(stop * SECOND)
for protocol in (EntanglementGenerationA, EntanglementGenerationB):
    protocol.set_global_type(parameters.get('protocol', BARRET_KOK))
topology = RouterNetTopo(config)
timeline = topology.get_timeline()
timeline.show_progress = False
if 'seed' in parameters:
    for offset, node in enumerate(node for nodes in topology.get_nodes().values() for node in nodes):
        node.set_seed(parameters['seed'] + offset)
apps = {node.name: RequestApp(node) for node in topology.get_nodes_by_type('QuantumRouter')}
timeline.init()
for request in parameters['requests']:
    source, target = request['source'], request['target']
    submit, start, end = (float(request[key]) * SECOND for key in ('submit', 'start', 'end'))
    size, fidelity = request['memories'], float(request['fidelity'])
    if source == target or source not in apps or target not in apps:
        raise ValueError('Request endpoints must be different router names in this topology.')
    if not all(map(isfinite, (submit, start, end))) or not 0 <= submit < start < end <= timeline.stop_time:
        raise ValueError('Request times must satisfy 0 <= submit < start < end <= simulation time.')
    if not isinstance(size, int) or isinstance(size, bool) or size < 1 or not 0 < fidelity <= 1:
        raise ValueError('Memories must be a positive integer; fidelity must be in (0, 1].')
    timeline.schedule(Event(int(submit), Process(apps[source], 'start',
        [target, int(start), int(end), size, fidelity])))

timeline.run()
print(json.dumps({'simulation_time_s': timeline.now() / SECOND, 'stop_time_s': stop,
                  'nodes': {name: {'delivered_pairs': app.memory_counter}
                            for name, app in apps.items()}}, indent=2))
