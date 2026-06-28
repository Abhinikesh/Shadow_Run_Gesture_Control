import sys
import queue
from game.engine import init_game, step_game, shutdown_game
from webcam.overlay_window import init_webcam, step_webcam, shutdown_webcam

def main():
    import threading
    stop_event = threading.Event()
    gesture_queue: queue.Queue = queue.Queue(maxsize=1)
    cap, detector = init_webcam(gesture_queue, stop_event)
    if cap is None:
        print('[main] Webcam failed to initialize — exiting.')
        sys.exit(1)
    game_state = init_game()
    try:
        while not stop_event.is_set():
            step_webcam(cap, detector, gesture_queue, stop_event)
            if stop_event.is_set():
                break
            step_game(game_state, gesture_queue, stop_event)
    except KeyboardInterrupt:
        print('\n[main] KeyboardInterrupt — shutting down.')
        stop_event.set()
    finally:
        shutdown_webcam(cap, detector)
        shutdown_game(game_state)
    print('[main] Shut down cleanly. Goodbye.')
    sys.exit(0)
if __name__ == '__main__':
    main()
