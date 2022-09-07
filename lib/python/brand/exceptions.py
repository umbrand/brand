# brand-specific exceptions
class GraphError(Exception):
    def __init__(self, graph_name='', err_str='', kill_nodes=True, source_exception=None):
        self.graph_name = graph_name
        self.err_str = err_str
        self.kill_nodes = kill_nodes
        self.source_exception = source_exception

    def __repr__(self):
        return f"GraphError(graph_name={self.graph_name}, err_str={self.err_str}, kill_nodes={self.kill_nodes}, source_exception={repr(self.source_exception)})"
    
class NodeError(Exception):
    def __init__(self, graph_name='', node_nickname='', err_str='', source_exception=None):
        self.graph_name = graph_name
        self.node_nickname = node_nickname
        self.err_str = err_str
        self.source_exception = source_exception

    def __repr__(self):
        return f"NodeError(graph_name={self.graph_name}, node_nickname={self.node_nickname}, err_str={self.err_str}, source_exception={repr(self.source_exception)})"

class RedisError(Exception):
    def __init__(self, err_str=''):
        self.err_str = err_str