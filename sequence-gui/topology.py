"""Translate the GUI's editable graph without discarding native SeQUeNCe settings."""
from copy import deepcopy

import networkx as nx
import numpy as np
import pandas as pd

from sequence.constants import SPEED_OF_LIGHT
from .graph_comp import GraphNode


def _delay(channel):
    delay, distance = float(channel.get('delay', 0)), float(channel.get('distance', 1000))
    if not np.isfinite([delay, distance]).all() or min(delay, distance) < 0:
        raise ValueError('Classical delays and distances must be finite and nonnegative.')
    return delay if delay > 0 else distance / SPEED_OF_LIGHT


def load_graph_data(network_in):
    if network_in.get('cconnections'):
        raise ValueError('Use directed cchannels instead of cconnections in the topology editor.')
    legacy = 'cchannels_table' in network_in
    nodes = network_in['nodes']
    names = [node['name'] for node in nodes]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError('Node names must be nonempty and unique.')
    graph = nx.DiGraph(config=deepcopy(network_in), legacy=legacy)
    for node in nodes:
        template = node.get('template', 'default_router' if legacy else '')
        data = GraphNode(node['name'], node['type'], template).__dict__
        graph.add_node(node['name'], label=node['name'], node_type=node['type'], data=data, config=deepcopy(node))
    for kind in ('qconnections', 'qchannels'):
        source_key, target_key = ('node1', 'node2') if kind == 'qconnections' else ('source', 'destination')
        for order, edge in enumerate(network_in.get(kind, [])):
            source, target = edge[source_key], edge[target_key]
            distance, attenuation = float(edge['distance']), float(edge['attenuation'])
            if (source not in graph or target not in graph or source == target or graph.has_edge(source, target)
                    or not np.isfinite([distance, attenuation]).all() or min(distance, attenuation) < 0):
                raise ValueError('Links need distinct existing endpoints, no parallel directed links, and nonnegative finite values.')
            graph.add_edge(source, target, kind=kind, order=order, config=deepcopy(edge),
                           data=dict(source=source, target=target, distance=distance,
                                     attenuation=attenuation, link_type='Quantum'))
    channels = network_in.get('cchannels', [])
    if legacy:
        table = network_in['cchannels_table']
        labels = table['labels']
        delays = np.asarray(table['table'], dtype=float)
        if (table.get('type', 'RT') != 'RT' or len(labels) != len(names) or set(labels) != set(names)
                or delays.shape != (len(names), len(names)) or not np.isfinite(delays).all() or (delays < 0).any()):
            raise ValueError('The RT delay table must match all nodes and contain finite nonnegative values.')
    else:
        labels = names
        delays = np.full((len(names), len(names)), np.nan)
        np.fill_diagonal(delays, 0)
        for channel in channels:
            source, target = channel['source'], channel['destination']
            if source not in graph or target not in graph or source == target:
                raise ValueError('Classical channels need distinct existing endpoints.')
            i, j = names.index(source), names.index(target)
            if not np.isnan(delays[i, j]):
                raise ValueError('Parallel directed classical channels cannot be edited as a delay table.')
            delays[i, j] = 2 * _delay(channel)
    tdm = np.full(delays.shape, 20000, dtype=int)
    np.fill_diagonal(tdm, 0)
    return graph, pd.DataFrame(delays, columns=labels), pd.DataFrame(tdm, columns=labels)


def graph_to_topology(graph, delays, templates):
    output = deepcopy(graph.graph.get('config', {}))
    legacy = graph.graph.get('legacy', True)
    output.pop('cchannels_table', None)
    native_templates = output.get('templates', {}).copy()

    def add_template(name, node_type):
        if not name or name in native_templates or name not in templates.get(node_type, {}):
            return
        values = templates[node_type][name]
        if node_type == 'QuantumRouter':
            memory = templates['Memory'][values['mem_type']].copy()
            memory['fidelity'] = memory.pop('raw_fidelity')
            if memory['coherence_time'] > 0:
                memory['coherence_time'] /= 1e12
            native_templates[name] = {'MemoryArray': memory}
        elif node_type == 'BSMNode':
            native_templates[name] = {'SingleAtomBSM': {'detectors': [
                {('time_resolution' if key == 'resolution' else key): value for key, value in templates['Detector'][values[key_name]].items()}
                for key_name in ('detector_1', 'detector_2')]}}
        else:
            raise ValueError(f'No native template conversion for {node_type}.')

    output['nodes'] = []
    previous_names = {}
    for name, node in graph.nodes(data=True):
        raw = deepcopy(node.get('config', {}))
        previous_names[name] = raw.get('name', name)
        data = node['data']
        raw.update(name=name, type=node['node_type'])
        if data['template']:
            raw['template'] = data['template']
            add_template(data['template'], node['node_type'])
        elif raw.get('template'):
            raw.pop('template')
        if legacy or 'config' not in node:
            raw.setdefault('seed', 0)
            if node['node_type'] == 'QuantumRouter' and 'memo_size' not in raw:
                raw['memo_size'] = templates['QuantumRouter'].get(data['template'], templates['QuantumRouter']['default_router'])['memo_size']
        output['nodes'].append(raw)
    quantum = {'qconnections': [], 'qchannels': []}
    for source, target, edge in graph.edges(data=True):
        kind = edge.get('kind', 'qconnections' if all(graph.nodes[n]['node_type'] == 'QuantumRouter' for n in (source, target)) else 'qchannels')
        source_key, target_key = ('node1', 'node2') if kind == 'qconnections' else ('source', 'destination')
        data, raw = edge['data'], deepcopy(edge.get('config', {}))
        distance, attenuation = float(data['distance']), float(data['attenuation'])
        if data['link_type'] != 'Quantum' or not np.isfinite([distance, attenuation]).all() or min(distance, attenuation) < 0:
            raise ValueError('Quantum links need finite nonnegative distance and attenuation.')
        raw.update({source_key: source, target_key: target, 'distance': distance, 'attenuation': attenuation})
        if kind == 'qconnections' and (legacy or 'config' not in edge):
            raw.setdefault('type', 'meet_in_the_middle')
            raw.setdefault('template', 'default_BSM')
            add_template(raw['template'], 'BSMNode')
        quantum[kind].append((edge.get('order', float('inf')), raw))
    for kind, channels in quantum.items():
        if channels or kind in output:
            output[kind] = [raw for _, raw in sorted(channels, key=lambda item: item[0])]
    if native_templates or 'templates' in output:
        output['templates'] = native_templates
    labels = list(delays.columns)
    if delays.shape != (len(graph), len(graph)) or set(labels) != set(graph):
        raise ValueError('Delay-table labels must match the current nodes.')
    original = {(c['source'], c['destination']): c for c in output.get('cchannels', [])}
    order = {ends: i for i, ends in enumerate(original)}
    channels = []
    for i, source in enumerate(labels):
        for j, target in enumerate(labels):
            delay = delays.iloc[i, j]
            if source == target or pd.isna(delay):
                continue
            delay = float(delay) / 2
            if not np.isfinite(delay) or delay < 0:
                raise ValueError('Classical delays must be finite and nonnegative; blank means no channel.')
            raw = deepcopy(original.get((previous_names[source], previous_names[target]), {}))
            if not raw or delay != _delay(raw):
                raw['delay'] = delay
                if delay == 0:
                    raw['distance'] = 0
            raw.update(source=source, destination=target)
            channels.append(raw)
    if channels or 'cchannels' in output or legacy:
        channels.sort(key=lambda c: order.get((previous_names[c['source']], previous_names[c['destination']]), len(order)))
        output['cchannels'] = channels
    return output
