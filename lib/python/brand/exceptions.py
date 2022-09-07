# brand-specific exceptions
class GraphError(Exception):
    def __init__(self, graph_name='', err_str='', source_exception=None):
        self.graph_name = graph_name
        self.err_str = err_str
        self.source_exception = source_exception

    def __repr__(self):
        return f"GraphError(graph_name={self.graph_name}, err_str={self.err_str}, source_exception={repr(self.source_exception)})"
    
class NodeError(Exception):
    def __init__(self, graph_name='', node_nickname='', err_str='', source_exception=None):
        self.graph_name = graph_name
        self.node_nickname = node_nickname
        self.err_str = err_str
        self.source_exception = source_exception

    def __repr__(self):
        return f"NodeError(graph_name={self.graph_name}, node_nickname={self.node_nickname}, err_str={self.err_str}, source_exception={repr(self.source_exception)})"

class BooterError(Exception):
    def __init__(self, machine='', graph_name='', err_str='', source_exception=''):
        self.machine = machine
        self.graph_name = graph_name
        self.err_str = err_str
        self.source_exception = source_exception
    
    def __repr__(self):
        return f"BooterError(machine={self.machine}, graph_name={self.graph_name}, err_str={self.err_str}, source_exception={repr(self.source_exception)})"

class RedisError(Exception):
    def __init__(self, err_str=''):
        self.err_str = err_str