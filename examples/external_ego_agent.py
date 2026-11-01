"""Minimal external ego agent for VSE (CARLA Python API only; no ROS, no VSE code).

What it does
  1. Spawns an ego vehicle with role_name "ego_vehicle" (VSE adopts it by role name).
  2. Listens for VSE's ego route events (HTTP POST, JSON) -- see vse_playback/ego_route_sink.py.
  3. On a "route" event: teleports the ego to the first waypoint, then drives toward the last
     waypoint (the destination) with a tiny pure-pursuit controller.
  4. On a "cancel" event: brakes and forgets the destination.
  5. Ticks the world itself if it is in synchronous mode (VSE waits for the tick in external mode).

Run it, then start VSE with the sink pointed here, and press Play:

    python examples/external_ego_agent.py --carla-host localhost --listen-port 8080
    VSE_EGO_ROUTE_SINK=http://localhost:8080/route python vse.py

Needs only the `carla` pip package (same version as the server) -- NOT CARLA's PythonAPI/carla
folder, so it runs in a bare container. If this runs in Docker and VSE on the host, publish the
port (-p 8080:8080) and use --carla-host host.docker.internal.

The driving here is deliberately crude: at each junction it follows the lane branch that gets
closest to the destination (no global route planning), so it can pick wrong turns on complex
maps. A real stack replaces `drive_step` with its own planner; the HTTP receiver stays the same.
"""

import argparse
import json
import math
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import carla

LOOKAHEAD_M = 6.0      # pure-pursuit lookahead distance
WHEELBASE_M = 2.9
MAX_STEER_RAD = 0.7    # steering angle that maps to steer = 1.0
ARRIVE_RADIUS_M = 3.0

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


def drive_step(world_map, ego, destination, target_speed_ms):
    """One control step toward `destination` (a carla.Location). Returns (control, arrived)."""
    transform, velocity = ego.get_transform(), ego.get_velocity()
    if transform.location.distance(destination) < ARRIVE_RADIUS_M:
        return carla.VehicleControl(brake=1.0), True

    # Lookahead point: follow the lane branch that ends up closest to the destination.
    candidates = world_map.get_waypoint(transform.location).next(LOOKAHEAD_M)
    target = min(candidates, key=lambda w: w.transform.location.distance(destination)) if candidates else None
    target_loc = target.transform.location if target else destination

    # Pure pursuit (CARLA frame: +yaw / +steer are clockwise, i.e. to the right).
    alpha = math.atan2(target_loc.y - transform.location.y, target_loc.x - transform.location.x) \
        - math.radians(transform.rotation.yaw)
    alpha = math.atan2(math.sin(alpha), math.cos(alpha))
    steer = math.atan2(2.0 * WHEELBASE_M * math.sin(alpha), LOOKAHEAD_M) / MAX_STEER_RAD
    speed_error = target_speed_ms - math.hypot(velocity.x, velocity.y)
    return carla.VehicleControl(
        steer=max(-1.0, min(1.0, steer)),
        throttle=max(0.0, min(0.75, 0.5 * speed_error)),
        brake=max(0.0, min(1.0, -0.5 * speed_error)),
    ), False


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

    destination = None
    world_map = world.get_map()
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
                    destination = carla.Location(dest["x"], dest["y"], dest["z"])
                    print(f"Driving to ({dest['x']:.1f}, {dest['y']:.1f}) from scenario '{event.get('scenario')}'")
                elif event.get("event") == "cancel":
                    destination = None
                    ego.apply_control(carla.VehicleControl(brake=1.0))
                    print("Route cancelled")

            if destination is not None:
                control, arrived = drive_step(world_map, ego, destination, args.speed / 3.6)
                ego.apply_control(control)
                if arrived:
                    destination = None
                    print("Destination reached")
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        ego.destroy()


if __name__ == "__main__":
    main()
