from .lib import *
import argparse

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('uri', help='URI to database (e.g. sqlite:///db.sqlite3).')
    parser.add_argument('--output-file', '-o', help='File to which to send output HTML.', default='schemaviz.html')

    args = parser.parse_args()

    graph = create_graph(args.uri)
    fig = create_plot()
    widgets = draw_graph(fig, graph)
    draw(widgets, args.output_file)
