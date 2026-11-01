"""Minimal external ego agent for VSE (CARLA Python API only; no ROS, no VSE code).

What it does
  1. Spawns an ego vehicle with role_name "ego_vehicle" (VSE adopts it by role name).
  2. Listens for VSE's ego route events (HTTP POST, JSON) -- see vse_playback/ego_route_sink.py.
  3. On a "route" event: teleports the ego to the first waypoint, then drives to the last
     waypoint (the destination) with CARLA's BasicAgent.
  4. On a "cancel" event: brakes and forgets the destination.
  5. Ticks the world itself if it is in synchronous mode (VSE waits for the tick in external mode).

Run it, then start VSE with the sink pointed here, and press Play:

    python examples/external_ego_agent.py --carla-host localhost --listen-port 8080
    VSE_EGO_ROUTE_SINK=http://localhost:8080/route python vse.py

Needs the `carla` module and CARLA's PythonAPI/carla on PYTHONPATH (for `agents.navigation`).
If this runs in Docker and VSE on the host, publish the port (-p 8080:8080) and use
--carla-host host.docker.internal.
"""

import argparse
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import carla
from agents.navigation.basic_agent import BasicAgent

events = queue.Queue()


class RouteHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            events.put(json.loads(self.rfile.read(length)))
            self.send_response(200)
        except ValueError:
            self.send_response(400)
        self.end_headers()

    def log_message(self, *args):  # keep the console quiet
        pass


def spawn_ego(world):
    blueprint = world.get_blueprint_library().filter("vehicle.tesla.model3")[0]
    blueprint.set_attribute("role_name", "ego_vehicle")
    for spawn_point in world.get_map().get_spawn_points():
        ego = world.try_spawn_actor(blueprint, spawn_point)
        if ego:
            return ego
    raise RuntimeError("No free spawn point for the ego")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--carla-host", default="localhost")
    parser.add_argument("--carla-port", type=int, default=2000)
    parser.add_argument("--listen-port", type=int, default=8080)
    parser.add_argument("--speed", type=float, default=30.0, help="target speed, km/h")
    args = parser.parse_args()

    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(10.0)
    world = client.get_world()
    ego = spawn_ego(world)
    print(f"Ego spawned (id {ego.id}); waiting for a route from VSE...")

    server = ThreadingHTTPServer(("0.0.0.0", args.listen_port), RouteHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    agent = None
    try:
        while True:
            # Synchronous world: we are the tick source. Asynchronous: just follow the server.
            if world.get_settings().synchronous_mode:
                world.tick()
            else:
                world.wait_for_tick()

            while not events.empty():
                event = events.get()
                if event.get("event") == "route" and event.get("waypoints"):
                    first, dest = event["waypoints"][0], event["destination"]
                    if not event.get("map", "").endswith(world.get_map().name.split("/")[-1]):
                        print(f"Warning: route is for map {event.get('map')}, world is {world.get_map().name}")
                    ego.set_transform(carla.Transform(
                        carla.Location(first["x"], first["y"], first["z"] + 0.5),
                        carla.Rotation(yaw=first["yaw"])))
                    agent = BasicAgent(ego, target_speed=args.speed)
                    agent.set_destination(carla.Location(dest["x"], dest["y"], dest["z"]))
                    print(f"Driving to ({dest['x']:.1f}, {dest['y']:.1f}) from scenario '{event.get('scenario')}'")
                elif event.get("event") == "cancel":
                    agent = None
                    ego.apply_control(carla.VehicleControl(brake=1.0))
                    print("Route cancelled")

            if agent is not None:
                if agent.done():
                    ego.apply_control(carla.VehicleControl(brake=1.0))
                    agent = None
                    print("Destination reached")
                else:
                    ego.apply_control(agent.run_step())
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        ego.destroy()


if __name__ == "__main__":
    main()
