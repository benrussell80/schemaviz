import os
from pprint import pp
from schemaviz import __version__, create_graph, create_widgets, draw
import sqlite3
from contextlib import contextmanager


def test_version():
    assert __version__ == '0.1.0'


DB_FILENAME = "schemaviz_test.db"

@contextmanager
def sqlite_con():
    exists = os.path.isfile(DB_FILENAME)
    try:
        con = sqlite3.connect(DB_FILENAME)
        cur = con.cursor()
        cur.execute('''\
        CREATE TABLE employee (
            id integer primary key,
            name text not null,
            role text not null,
            location_id integer not null,
            supervisor_id integer,
            FOREIGN KEY(supervisor_id) REFERENCES employee(id),
            FOREIGN KEY(location_id) REFERENCES location(id)
        );
        ''')

        cur.execute('''\
        CREATE TABLE location (
            id integer primary key,
            name text not null,
            manager_id integer not null,
            FOREIGN KEY(manager_id) REFERENCES employee(id)
        );
        ''')
        con.commit()
        cur.close()
        yield con
    finally:
        con.close()
        if not exists:
            os.remove('schemaviz_test.db')


def main():
    with sqlite_con() as con:
        uri = f'sqlite:///{DB_FILENAME}'
        graph = create_graph(uri)
        widgets = create_widgets(graph)
        draw(widgets, 'test.html')


if __name__ == '__main__':
    main()