"""Planar body-frame translation, followed by a yaw update in radians."""
import math


def wrap_angle(value):
    if not math.isfinite(value):
        raise ValueError("Yaw must be finite")
    return (value + math.pi) % (2*math.pi) - math.pi


def world_delta_to_local(action, current_yaw):
    dx, dy, dyaw = map(float, action)
    c, s = math.cos(current_yaw), math.sin(current_yaw)
    return [c*dx+s*dy, -s*dx+c*dy, wrap_angle(dyaw)]


def integrate(actions, initial_pose=(0., 0., 0.)):
    x, y, yaw = map(float, initial_pose)
    if not all(math.isfinite(v) for v in (x,y,yaw)):
        raise ValueError("Initial pose must be finite")
    xy, headings = [[x,y]], [yaw]
    for action in actions:
        if len(action) != 3 or not all(math.isfinite(v) for v in action):
            raise ValueError("Actions require three finite values")
        dx, dy, dyaw = action
        x, y = x+math.cos(yaw)*dx-math.sin(yaw)*dy, y+math.sin(yaw)*dx+math.cos(yaw)*dy
        yaw += wrap_angle(dyaw)
        xy.append([x,y]); headings.append(yaw)
    return xy, headings


def reference_actions(position, yaw):
    if len(position) != len(yaw) or len(position) < 2:
        raise ValueError("Reference requires matching position/yaw and at least two poses")
    # Promote before subtraction: float32 deltas otherwise lose precision.
    return [world_delta_to_local([float(b[0])-float(a[0]),float(b[1])-float(a[1]),float(yb)-float(ya)],float(ya))
            for a,b,ya,yb in zip(position,position[1:],yaw,yaw[1:])]


def canonical_reference(position, yaw):
    """Evaluation-only: remove reference initial pose; never pass it to the model."""
    return integrate(reference_actions(position,yaw))
