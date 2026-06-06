from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import chain
from typing import cast, Dict, Iterator, List, Optional, Tuple

from artifactsmmo.client.client import Client
from artifactsmmo.extensions.MapSchemaExtension import MapSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ActiveEventSchema, ConditionSchema, EventSchema, MapSchema
from artifactsmmo.singleton import SingletonMeta


@dataclass
class Route:
    from_cluster: str
    to_cluster: str
    gateways: List[MapSchemaExtension]
    conditions: List[List[ConditionSchema]]
    is_same_cluster: bool

    @classmethod
    def is_same_cluster(cls, from_cluster: str, to_cluster: str):
        return cls(from_cluster, to_cluster, [], [], True)


@dataclass
class Gateway:
    from_cluster: str
    from_map: int
    to_map: int
    to_cluster: str
    gateway_obj: MapSchemaExtension


class MapService(metaclass=SingletonMeta):
    def __init__(self, client: Client):
        self.client = client
        self.map_tiles: Dict[Tuple[str, int, int], MapSchemaExtension] = {}
        self.map_tiles_by_id: Dict[int, MapSchemaExtension] = {}
        self.map_tiles_by_type: Dict[str, Dict[str, List[MapSchemaExtension]]] = defaultdict(lambda: defaultdict(list))
        self.routes_map: Dict[str, Dict[str, Route]] = {}

    def init_maps(self):
        with ThreadPoolExecutor() as executor:
            f_maps = executor.submit(self.client.get_all_maps)
            f_active = executor.submit(self.client.get_active_events)
            f_all = executor.submit(self.client.get_all_events)

            all_maps = cast(List[MapSchema], f_maps.result())
            active_events = cast(List[ActiveEventSchema], f_active.result())
            all_events = cast(List[EventSchema], f_all.result())

        all_map_tiles: Dict[int, MapSchema] = {m.map_id: m for m in all_maps}

        for active_event in active_events:
            all_map_tiles[active_event.previous_map.map_id] = active_event.previous_map

        layer_map: Dict[str, List[MapSchema]] = defaultdict(list)
        for map_tile in all_map_tiles.values():
            layer_map[str(map_tile.layer)].append(map_tile)

            # if map_tile.interactions.transition and map_tile.interactions.transition.conditions:
            #    for condition in map_tile.interactions.transition.conditions:
            #        logger.info(f'{condition.code} {condition.operator} {condition.value}')

        map_tile_extensions: List[MapSchemaExtension] = self.__process_layers(layer_map)
        for map_tile in map_tile_extensions:
            self.map_tiles_by_id[map_tile.map_id] = map_tile
            self.map_tiles[str(map_tile.layer), map_tile.x, map_tile.y] = map_tile
            if map_tile.interactions.content:
                self.map_tiles_by_type[str(map_tile.interactions.content.type)][map_tile.interactions.content.code].append(map_tile)

        gateways: List[Gateway] = self.__find_gateways(self.map_tiles_by_id)
        routes: List[Route] = self.__find_routes(gateways)
        for route in routes:
            if route.from_cluster not in self.routes_map:
                self.routes_map[route.from_cluster] = {}
            self.routes_map[route.from_cluster][route.to_cluster] = route

        for event in all_events:
            for event_map in event.maps:
                self.map_tiles_by_id[event_map.map_id].event_content[event.code] = event.content.code

    def get_map_by_id(self, map_id: int) -> MapSchemaExtension:
        if not self.map_tiles_by_id:
            self.init_maps()

        return self.map_tiles_by_id[map_id]

    def get_all_maps(self) -> Iterator[MapSchemaExtension]:
        if not self.map_tiles:
            self.init_maps()
        for map_tile in self.map_tiles.values():
            yield map_tile

    def get_map(self, layer: str, x: int, y: int) -> Optional[MapSchemaExtension]:
        if not self.map_tiles:
            self.init_maps()

        cached_map = self.map_tiles.get((layer, x, y))
        if cached_map:
            return cached_map
        else:
            logger.warning(f'Could not retrieve map={layer}/{x}/{y} from cache.')
            return self.client.get_map(layer, x, y)  # FIXME: Will not contain layer-id!

    def get_maps(self, content_type: str, content_code: str = None) -> List[MapSchemaExtension]:
        if not self.map_tiles_by_type:
            self.init_maps()

        if content_code:
            result = self.map_tiles_by_type[content_type][content_code]
        else:
            result = list(chain.from_iterable(self.map_tiles_by_type[content_type].values()))
        # if not result:
        #     logger.info(f'No maps found for content_type={content_type} and content_code={content_code}. Checking (cached) backend.')
        #     result = self.client.get_maps(content_type, content_code)
        return result

    def get_route(self, from_cluster: str, to_cluster: str) -> Optional[Route]:
        if not self.routes_map:
            self.init_maps()

        if from_cluster not in self.routes_map or to_cluster not in self.routes_map[from_cluster]:
            logger.error(f'Could not find route for from_cluster={from_cluster}, to_cluster={to_cluster}')
            return None

        return self.routes_map[from_cluster][to_cluster]

    def __process_layers(self, layer_map: Dict[str, List[MapSchema]]) -> List[MapSchemaExtension]:
        map_tile_extensions: List[MapSchemaExtension] = []
        for layer, map_tiles in layer_map.items():
            cluster_id_map, x_min, x_max, y_min, y_max, map_tile_list = self.cluster_map_tiles_from_objects(layer, map_tiles)
            map_tile_extensions.extend(map_tile_list)
            # self.__print_clusters(layer, cluster_id_map, x_min, x_max, y_min, y_max)
        return map_tile_extensions

    @staticmethod
    def cluster_map_tiles_from_objects(
        layer: str, tile_objects: List[MapSchema]
    ) -> Tuple[Dict[Tuple[int, int], int], int, int, int, int, List[MapSchemaExtension]]:
        tile_map = {}
        x_coords = []
        y_coords = []
        for tile in tile_objects:
            x = tile.x
            y = tile.y
            x_coords.append(x)
            y_coords.append(y)
            tile_map[(x, y)] = tile.access.type == 'blocked'

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        cluster_id_map = {}
        next_cluster_id = 0

        def get_adjacent_coordinates(x, y):
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:  # N,S,W,E
                nx, ny = x + dx, y + dy
                if (nx, ny) in tile_map:  # only consider existing tiles
                    yield nx, ny

        def depth_first_search_assign_cluster(start_x, start_y, cluster_id):
            stack = [(start_x, start_y)]
            while stack:
                current_x, current_y = stack.pop()
                if (current_x, current_y) in cluster_id_map:
                    continue  # already assigned
                cluster_id_map[(current_x, current_y)] = cluster_id
                for neighbor_x, neighbor_y in get_adjacent_coordinates(current_x, current_y):
                    if not tile_map[(neighbor_x, neighbor_y)] and (neighbor_x, neighbor_y) not in cluster_id_map:
                        stack.append((neighbor_x, neighbor_y))

        for (x, y), is_blocked in tile_map.items():
            if not is_blocked and (x, y) not in cluster_id_map:
                depth_first_search_assign_cluster(x, y, next_cluster_id)
                next_cluster_id += 1

        for (x, y), is_blocked in tile_map.items():
            if is_blocked:
                cluster_id_map[(x, y)] = -1

        map_tile_extensions: List[MapSchemaExtension] = []
        for tile in tile_objects:
            cluster_id = cluster_id_map[(tile.x, tile.y)]
            cluster_id_str = f'{layer}-{cluster_id}' if cluster_id >= 0 else None
            map_tile_extensions.append(MapSchemaExtension(tile, cluster_id_str))

        return cluster_id_map, x_min, x_max, y_min, y_max, map_tile_extensions

    @staticmethod
    def __print_clusters(layer: str, cluster_id_map, x_min, x_max, y_min, y_max):
        color_emojis = ['🟩', '🟨', '🟪', '🟧', '🟫', '⬜']
        blocked_emoji = '⬛'

        output_lines = [layer]
        for y in range(y_min, y_max + 1):
            line = ''
            for x in range(x_min, x_max + 1):
                cid = cluster_id_map.get((x, y), -1)
                if cid == -1:
                    line += blocked_emoji
                else:
                    line += color_emojis[cid % len(color_emojis)]
            output_lines.append(line)

        logger.info('\n'.join(output_lines))

    @staticmethod
    def __find_gateways(map_tiles_by_id: Dict[int, MapSchemaExtension]) -> List[Gateway]:
        gateways: List[Gateway] = []
        for map_tile in map_tiles_by_id.values():
            if map_tile.interactions and map_tile.interactions.transition:
                gateway = Gateway(
                    from_cluster=map_tile.cluster_id,
                    from_map=map_tile.map_id,
                    to_map=map_tile.interactions.transition.map_id,
                    to_cluster=map_tiles_by_id[map_tile.interactions.transition.map_id].cluster_id,
                    gateway_obj=map_tile,
                )
                gateways.append(gateway)
        return gateways

    @staticmethod
    def __find_routes(gateways: List[Gateway]) -> List[Route]:
        # Build a directed graph of clusters
        directed_graph = defaultdict(set)
        for g in gateways:
            directed_graph[g.from_cluster].add(g.to_cluster)
            # no reverse edge unless explicitly present in gateways

        # DFS: all paths between two clusters (directed)
        def all_paths(graph, start, end, path=None):
            if path is None:
                path = []
            path = path + [start]
            if start == end:
                return [path]
            if start not in graph:
                return []
            paths = []
            for node in graph[start]:
                if node not in path:  # avoid cycles
                    new_paths = all_paths(graph, node, end, path)
                    for p in new_paths:
                        paths.append(p)
            return paths

        clusters = set()
        for g in gateways:
            clusters.add(g.from_cluster)
            clusters.add(g.to_cluster)
        clusters = list(clusters)

        # Helper: find gateways between two clusters in a given direction
        def find_gateways_between(c1, c2):
            return [g.gateway_obj for g in gateways if g.from_cluster == c1 and g.to_cluster == c2]

        all_routes = []
        for i, start in enumerate(clusters):
            for end in clusters:  # allow every pair (directed)
                if start == end:
                    continue
                paths = all_paths(directed_graph, start, end)
                for path in paths:
                    route_gateways = []
                    for a, b in zip(path, path[1:]):  # each hop
                        gws = find_gateways_between(a, b)
                        route_gateways.extend(gws)
                    route_obj = Route(
                        from_cluster=path[0],
                        to_cluster=path[-1],
                        gateways=route_gateways,
                        conditions=[gwo.interactions.transition.conditions for gwo in route_gateways],
                        is_same_cluster=path[0] == path[-1],
                    )
                    all_routes.append(route_obj)

        return all_routes
