import json
import os

import networkx as nx
import pandas as pd

from .app import QuantumGUI
from .topology import load_graph_data


class RunGui:
    DEFAULT_CONFIG = '/starlight.json'

    def __init__(self, name):
        graph = nx.DiGraph()
        tdm_table = pd.DataFrame()
        delay_table = pd.DataFrame()
        self.name = name
        self.gui = QuantumGUI(
            graph,
            delays=delay_table,
            tdm=tdm_table
        ).get_app(name)

    def load_graph(self, path_to_topology=None):
        if path_to_topology is None:
            path_to_topology = os.path.dirname(__file__) + RunGui.DEFAULT_CONFIG
        with open(path_to_topology, encoding='utf-8-sig') as json_file:
            graph, delay_table, tdm_table = load_graph_data(json.load(json_file))
        self.gui = QuantumGUI(graph, delays=delay_table, tdm=tdm_table).get_app(self.name)
