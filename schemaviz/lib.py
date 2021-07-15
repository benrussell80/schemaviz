from bokeh.models.renderers import GraphRenderer
import numpy as np
from pprint import pp
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict

import networkx as nx
from bokeh.io import output_file, show
from bokeh.layouts import column, row
from bokeh.models.callbacks import CustomJS
from bokeh.models.glyphs import Circle, MultiLine
from bokeh.models.graphs import NodesAndLinkedEdges, StaticLayoutProvider
from bokeh.models.layouts import LayoutDOM
from bokeh.models.sources import ColumnDataSource
from bokeh.models.tools import BoxSelectTool, HoverTool, InspectTool, TapTool
from bokeh.models.widgets.markups import Div
from bokeh.models.widgets.tables import DataTable, TableColumn
from bokeh.palettes import Cividis11
from bokeh.plotting.figure import figure, Figure
from bokeh.plotting import from_networkx
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.reflection import Inspector


__all__ = [
    'create_graph',
    'create_plot',
    'graph_layout',
    'draw_graph',
    'draw',
]

class Fk(TypedDict):
    name: Optional[str]
    constrained_columns: List[str]
    referred_schema: Optional[Any]
    referred_table: str
    referred_columns: List[str]
    options: Dict


class Column(TypedDict):
    name: str
    type: Any
    nullable: bool
    default: Optional[Any]
    autoincrement: str
    primary_key: int


def create_graph(uri: str) -> nx.Graph:
    # connect to db
    engine = create_engine(uri)
    inspector: Inspector = inspect(engine)

    # create nx graph
    # - nodes are tables
    # - edges are foreign keys between those tables
    G = nx.DiGraph()

    # insert data into nx graph
    table_names = inspector.get_table_names()
    G.add_nodes_from(table_names)
    nx.set_node_attributes(G, {name: str(name) for name in table_names}, 'name')

    for name in table_names:
        # get table columns
        columns: List[Column] = inspector.get_columns(name)
        node = G.nodes[name]

        node['name'] = name
        node['columns'] = [
            {
                key: value if key != 'type' and key != 'default' else str(value)
                for key, value in col.items()
            } for col in columns
        ]
        
        # get table foreign keys
        fks: List[Fk] = inspector.get_foreign_keys(name)
        fk_list = []
        for fk in fks:
            attrs = fk.copy()
            attrs.pop('options')
            name2 = attrs['referred_table']
            G.add_edge(
                name,
                name2
            )
            fk_list.append(attrs)
        G.nodes[name]['fks'] = fk_list

    return G

def create_plot(figure_options: Optional[Dict] = None, tooltips: Optional[Iterable[InspectTool]] = None) -> Figure:
    figure_defaults = dict(
        title='Schemaviz',
        x_range=(-2, 2),
        y_range=(-2, 2),
    )

    plot = figure(**figure_defaults | (figure_options or {}))

    tooltip_defaults = [
        HoverTool(
            tooltips=[
                ('Type', 'Table'),
                ('Name', '@name'),
            ]
        ),
        TapTool(),
        BoxSelectTool()
    ]
    plot.add_tools(*(tooltips if tooltips is not None else tooltip_defaults))

    return plot

def path(start: np.ndarray, end: np.ndarray, steps: int, self_loop: bool = False):
    angle_start = np.arctan(start[1] / start[0])
    if start[0] < 0:
        angle_start += np.pi
    # else:
    #     angle_start -= np.pi

    angle_end = np.arctan(end[1] / end[0])
    if end[0] < 0:
        angle_end += np.pi
    # else:
    #     angle_end -= np.pi

    if self_loop:
        # center of path should be just outside the circle
        orig_radius = np.linalg.norm(start)
        center_x, center_y = orig_radius * 1.2 * start

        radius = 0.2 * orig_radius
        
        theta_1 = angle_start + np.pi
        theta_2 = angle_start + np.pi
        angles = np.linspace(theta_1 + np.pi / 12, theta_2 + 2 * np.pi - np.pi / 12, num=steps)
        xs = np.cos(angles) * radius + center_x
        ys = np.sin(angles) * radius + center_y
    else:
        vecx, vecy = end - start

        angle = np.pi / 3
        newx = vecx * np.cos(angle) - vecy * np.sin(angle)
        newy = vecx * np.sin(angle) + vecy * np.cos(angle)

        center = np.array([newx, newy]) + start

        # calc angle from center to start
        vec_to_start = start - center

        angle_to_start = np.arctan(vec_to_start[1] / vec_to_start[0])
        if vec_to_start[0] < 0:
            if vec_to_start[1] < 0:
                angle_to_start -= np.pi
            else:
                angle_to_start += np.pi

        # calc angle from center to end
        vec_to_end = end - center

        angle_to_end = np.arctan(vec_to_end[1] / vec_to_end[0])
        if vec_to_end[0] < 0:
            if vec_to_end[1] < 0:
                angle_to_end -= np.pi
            else:
                angle_to_end += np.pi

        radius = np.linalg.norm(center - start)
        angles = np.linspace(angle_to_start, angle_to_end, num=steps)
        xs = np.cos(angles) * radius + center[0]
        ys = np.sin(angles) * radius + center[1]

    return xs, ys

def graph_layout(g: nx.Graph) -> Dict:
    return nx.circular_layout(g)
    locs = {}
    for i, comp in enumerate(nx.connected_components(g)):
        sg = g.subgraph(comp)
        locs |= nx.circular_layout(sg, scale=1, center=(i, 0))

    return locs

# TODO: change these Dict's to helpful typed dicts
def draw_graph(fig: Figure, G: nx.DiGraph, node_options: Optional[Dict] = None, edge_options: Optional[Dict] = None) -> GraphRenderer:  # -> LayoutDOM:
    # add nodes
    locations = graph_layout(G)

    graph = from_networkx(G, locations)

    default_node_options = dict(
        size=15,
        fill_color=Cividis11[10]
    )
    graph.node_renderer.glyph = Circle(**default_node_options | (node_options or {}))

    xs = []
    ys = []

    starts = graph.edge_renderer.data_source.data['start']
    ends = graph.edge_renderer.data_source.data['end']
    for start, end in zip(starts, ends):
        xs_path, ys_path = path(locations[start], locations[end], 30, start == end)
        xs.append(xs_path)
        ys.append(ys_path)
    graph.edge_renderer.data_source.data['xs'] = xs
    graph.edge_renderer.data_source.data['ys'] = ys

    default_edge_options = dict(
        line_color=Cividis11[0],
        line_alpha=0.6,
        line_width=5,
    )

    graph.edge_renderer.glyph = MultiLine(**default_edge_options | (edge_options or {}))

    graph.inspection_policy = NodesAndLinkedEdges()
    graph.selection_policy = NodesAndLinkedEdges()

    fig.renderers.append(graph)

    # Data Tables
    table_columns = [
        TableColumn(field='name', title='Name')
    ]

    table_data_table = DataTable(
        source=graph.node_renderer.data_source,
        columns=table_columns,
        sizing_mode='stretch_both'
    )

    column_keys = [
        'name',
        'type',
        'nullable',
        'default',
        'autoincrement',
        'primary_key',
    ]
    column_columns = [
        TableColumn(field=key, title=key.title().replace('_', ' '))
        for key in column_keys
    ]

    column_cds = ColumnDataSource({
        key: [] for key in column_keys
    })

    column_data_table = DataTable(
        source=column_cds,
        columns=column_columns,
        sizing_mode='stretch_both',
    )

    fk_keys = [
        'name',
        'constrained_columns',
        'referred_schema',
        'referred_table',
        'referred_columns',
    ]
    fk_columns = [
        TableColumn(field=key, title=key.title().replace('_', ' '))
        for key in fk_keys
    ]
    fk_cds = ColumnDataSource({
        key: [] for key in fk_keys
    })

    fk_data_table = DataTable(
        source=fk_cds,
        columns=fk_columns,
        sizing_mode='stretch_both'
    )

    # Callbacks
    graph.node_renderer.data_source.selected.js_on_change('indices', CustomJS(
        args={
            'column_cds': column_cds,
            'graph_cds': graph.node_renderer.data_source,
            'fk_cds': fk_cds,
        },
        code="""
            // clear column data table
            Object.entries(column_cds.data).forEach(([_, array]) => {
                array.length = 0;
            })

            // clear fk data table
            console.log(fk_cds.data)
            console.log(graph_cds.data)
            Object.entries(fk_cds.data).forEach(([_, array]) => {
                array.length = 0;
            })

            // for each selected index
            for (let index of graph_cds.selected.indices) {
                // find the 'columns' attribute for that index
                let columns = graph_cds.data['columns'][index]

                // for each object in that array of objects
                columns.forEach(col => {
                    // push the data into the correct column so it shows up on the "Columns" data table
                    Object.entries(column_cds.data).forEach(([key, array]) => {
                        array.push(col[key])
                    })
                })

                // ...also find the foreign keys for that index
                let fks = graph_cds.data['fks'][index]
                console.log(JSON.stringify(fks))
                console.log(Object.keys(fk_cds.data))

                fks.forEach(fk => {
                    Object.entries(fk_cds.data).forEach(([key, array]) => {
                        array.push(fk[key])
                    })
                })
            }
            column_cds.change.emit();
            fk_cds.change.emit();
        """
    ))

    # output to file
    layout = row(
        fig, column(
            Div(text="Tables"),
            table_data_table,
            Div(text="Columns"),
            column_data_table
        ),
        column(
            Div(text='Foreign Keys'),
            fk_data_table
        )
    )

    return layout

def draw(layout: LayoutDOM, file: Optional[str] = None):
    if file is not None:
        output_file(file)

    show(layout)
