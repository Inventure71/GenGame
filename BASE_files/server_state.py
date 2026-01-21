#!/usr/bin/env python3
"""
Server-side game state serialization and broadcast helpers.
"""

from __future__ import annotations

import pickle
import time
import zlib
from typing import Dict, List, Set, Tuple, Optional, Any

try:
    import msgpack
except ImportError:  # pragma: no cover - optional dependency
    msgpack = None


class ServerStateManager:
    def __init__(self, server):
        self.server = server

    def _round_state_value(self, value: Any) -> Any:
        if callable(value):
            return None
        if isinstance(value, float):
            return round(value, 2)
        if isinstance(value, list):
            return [self._round_state_value(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self._round_state_value(v) for v in value)
        if isinstance(value, set):
            return [self._round_state_value(v) for v in value]
        if isinstance(value, frozenset):
            return [self._round_state_value(v) for v in value]
        if isinstance(value, dict):
            rounded = {}
            for key, val in value.items():
                if callable(key):
                    safe_key = str(key)
                elif isinstance(key, (str, int, float, bool)) or key is None:
                    safe_key = key
                else:
                    safe_key = str(key)
                rounded[safe_key] = self._round_state_value(val)
            return rounded
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value)
        if isinstance(value, (str, int, bool)) or value is None:
            return value
        return repr(value)

    def _round_state(self, state: dict) -> dict:
        return self._round_state_value(state)

    def _collect_current_entity_states(self) -> Dict[str, List[dict]]:
        character_states = []
        for char in self.server.arena.characters:
            char_state = char.__getstate__()
            controlling_player = None
            for player_id, char_id in self.server.player_id_to_character.items():
                if char_id == char.id:
                    controlling_player = player_id
                    break
            if controlling_player:
                char_state['last_input_id'] = self.server.last_input_ids.get(controlling_player, 0)
            else:
                char_state['last_input_id'] = 0
            character_states.append(self._round_state(char_state))

        return {
            'characters': character_states,
            'projectiles': [self._round_state(proj.__getstate__()) for proj in self.server.arena.projectiles],
            'weapons': [self._round_state(weapon.__getstate__()) for weapon in self.server.arena.weapon_pickups],
            'ammo_pickups': [self._round_state(ammo.__getstate__()) for ammo in self.server.arena.ammo_pickups],
            'platforms': [self._round_state(platform.__getstate__()) for platform in self.server.arena.platforms],
        }

    def _build_entity_map(self, entity_lists: Dict[str, List[dict]]) -> Dict[str, Dict[str, dict]]:
        entity_map: Dict[str, Dict[str, dict]] = {}
        for entity_type, entities in entity_lists.items():
            entity_map[entity_type] = {}
            for entity_data in entities:
                network_id = entity_data.get('network_id')
                if network_id:
                    entity_map[entity_type][network_id] = entity_data
        return entity_map

    def _build_class_registry(self, entity_lists: Dict[str, List[dict]]) -> Tuple[Dict[int, Dict[str, str]], Dict[Tuple[str, str], int]]:
        registry: Dict[int, Dict[str, str]] = {}
        reverse: Dict[Tuple[str, str], int] = {}
        next_id = 1

        for entities in entity_lists.values():
            for entity in entities:
                module_path = entity.get('module_path')
                class_name = entity.get('class_name')
                if not module_path or not class_name:
                    continue
                key = (module_path, class_name)
                if key not in reverse:
                    reverse[key] = next_id
                    registry[next_id] = {'module_path': module_path, 'class_name': class_name}
                    next_id += 1
                entity['class_id'] = reverse[key]
        return registry, reverse

    def _serialize_state_payload(self, payload: dict, serialization: str) -> bytes:
        if serialization == 'msgpack' and msgpack is not None:
            return msgpack.packb(payload, use_bin_type=True)
        return pickle.dumps(payload, protocol=4)

    def _encode_game_state_message(self, payload: dict, message_type: int, serialization: str, compress: bool) -> Tuple[dict, int, int]:
        serialized = self._serialize_state_payload(payload, serialization)
        raw_size = len(serialized)
        if compress:
            compressed_payload = zlib.compress(serialized, level=1)
        else:
            compressed_payload = serialized
        message = {
            'type': 'game_state',
            'message_type': message_type,
            'serialization': serialization,
            'compressed': compress,
            'payload': compressed_payload,
        }
        return message, raw_size, len(compressed_payload)

    def _record_state_stats(self, message_type: int, raw_size: int, compressed_size: int):
        bucket = 'full' if message_type == 1 else 'delta'
        self.server.state_stats[bucket]['raw'] += raw_size
        self.server.state_stats[bucket]['compressed'] += compressed_size
        self.server.state_stats[bucket]['count'] += 1

        if self.server.frame_counter % self.server.state_stats_log_interval == 0:
            self._log_state_stats()

    def _log_state_stats(self):
        for bucket in ('full', 'delta'):
            stats = self.server.state_stats[bucket]
            if stats['count'] == 0:
                continue
            avg_raw = stats['raw'] / stats['count']
            avg_comp = stats['compressed'] / stats['count']
            ratio = avg_comp / avg_raw if avg_raw else 0.0
            print(f"[net] {bucket} avg raw={avg_raw:.1f}B avg compressed={avg_comp:.1f}B ratio={ratio:.2f}")

    def _select_serialization(self, player_id: str) -> str:
        if not self.server.enable_msgpack or msgpack is None:
            return 'pickle'
        caps = self.server.client_capabilities.get(player_id, {})
        if caps.get('supports_msgpack'):
            return 'msgpack'
        return 'pickle'

    def _client_supports_delta(self, player_id: str) -> bool:
        caps = self.server.client_capabilities.get(player_id, {})
        return bool(caps.get('supports_delta'))

    def _client_supports_compression(self, player_id: str) -> bool:
        caps = self.server.client_capabilities.get(player_id, {})
        return bool(caps.get('supports_compression'))

    def _compute_delta_payload(
        self,
        player_id: str,
        current_lists: Dict[str, List[dict]],
        current_map: Dict[str, Dict[str, dict]],
        static_update: bool,
        game_over: bool,
        winner_id: Optional[str],
    ) -> Tuple[Optional[dict], bool, List[str]]:
        last_cache = self.server.client_state_cache.get(player_id)
        if not last_cache:
            return None, True, []

        class_reverse = self.server.client_class_registry_reverse.get(player_id, {})
        static_types = {'platforms', 'weapons', 'ammo_pickups'}
        removed_ids: Set[str] = set()
        current_ids = set()
        for entity_type, entity_map in current_map.items():
            current_ids.update(entity_map.keys())
        for entity_type, cached_entities in last_cache.items():
            for network_id in cached_entities.keys():
                if network_id not in current_ids:
                    removed_ids.add(network_id)

        payload: Dict[str, Any] = {
            'game_over': game_over,
            'removed_entities': list(removed_ids),
            'timestamp': round(time.time(), 2),
        }
        if game_over and winner_id:
            payload['winner_id'] = winner_id

        for entity_type, entities in current_lists.items():
            if entity_type in static_types and not static_update:
                payload[entity_type] = None
                continue

            deltas = []
            cached_entities = last_cache.get(entity_type, {})
            for entity_state in entities:
                network_id = entity_state.get('network_id')
                if not network_id:
                    continue

                cached_state = cached_entities.get(network_id)
                if not cached_state:
                    delta_state = dict(entity_state)
                    module_path = entity_state.get('module_path')
                    class_name = entity_state.get('class_name')
                    class_id = class_reverse.get((module_path, class_name))
                    if class_id is None:
                        return None, True, list(removed_ids)
                    delta_state['class_id'] = class_id
                    for key in self.server.delta_excluded_fields:
                        delta_state.pop(key, None)
                    deltas.append(delta_state)
                    continue

                changed = {'network_id': network_id}
                for key, value in entity_state.items():
                    if key in self.server.delta_excluded_fields:
                        continue
                    if key not in cached_state or value != cached_state[key]:
                        changed[key] = value
                if len(changed) > 1:
                    deltas.append(changed)

            payload[entity_type] = deltas

        return payload, False, list(removed_ids)

    def _update_client_state_cache(
        self,
        player_id: str,
        current_map: Dict[str, Dict[str, dict]],
        removed_ids: List[str],
        static_update: bool,
        message_type: int,
    ):
        static_types = {'platforms', 'weapons', 'ammo_pickups'}
        cache = self.server.client_state_cache.setdefault(player_id, {})

        if message_type == 1:
            for entity_type, entity_map in current_map.items():
                cache[entity_type] = dict(entity_map)
        else:
            for entity_type, entity_map in current_map.items():
                if entity_type in static_types and not static_update:
                    continue
                cache[entity_type] = dict(entity_map)

        if removed_ids:
            for entity_type in cache:
                for network_id in removed_ids:
                    cache[entity_type].pop(network_id, None)

    def _send_full_state(
        self,
        player_id: str,
        client_socket,
        current_lists: Dict[str, List[dict]],
        current_map: Dict[str, Dict[str, dict]],
        game_over: bool,
        winner_id: Optional[str],
    ):
        full_lists = {key: [dict(item) for item in value] for key, value in current_lists.items()}
        class_registry, reverse = self._build_class_registry(full_lists)
        payload = {
            'timestamp': round(time.time(), 2),
            **full_lists,
            'game_over': game_over,
            'class_registry': class_registry,
        }
        if game_over and winner_id:
            payload['winner_id'] = winner_id

        serialization = self._select_serialization(player_id)
        compress = self.server.enable_compression and self._client_supports_compression(player_id)
        message, raw_size, compressed_size = self._encode_game_state_message(payload, 1, serialization, compress)
        data = pickle.dumps(message, protocol=4)
        length_bytes = len(data).to_bytes(4, byteorder='big')
        self.server._send_data_safe(client_socket, length_bytes + data)

        self._record_state_stats(1, raw_size, compressed_size)
        self.server.client_class_registry[player_id] = class_registry
        self.server.client_class_registry_reverse[player_id] = reverse
        self._update_client_state_cache(player_id, current_map, [], True, 1)
        self.server.requested_full_state.discard(player_id)

    def _send_delta_state(
        self,
        player_id: str,
        client_socket,
        payload: dict,
        current_map: Dict[str, Dict[str, dict]],
        removed_ids: List[str],
        static_update: bool,
    ):
        serialization = self._select_serialization(player_id)
        compress = self.server.enable_compression and self._client_supports_compression(player_id)
        message, raw_size, compressed_size = self._encode_game_state_message(payload, 0, serialization, compress)
        data = pickle.dumps(message, protocol=4)
        length_bytes = len(data).to_bytes(4, byteorder='big')
        self.server._send_data_safe(client_socket, length_bytes + data)

        self._record_state_stats(0, raw_size, compressed_size)
        self._update_client_state_cache(player_id, current_map, removed_ids, static_update, 0)

    def broadcast_game_state(self):
        if not self.server.arena or not self.server.clients:
            return

        if not set(self.server.clients.keys()).issubset(self.server.clients_file_sync_ack):
            return

        if self.server.arena.game_over and not self.server.waiting_for_restart:
            self.server.game_finished_time = time.time()
            self.server.waiting_for_restart = True

            winner_name = self.server.arena.winner.id if self.server.arena.winner and hasattr(self.server.arena.winner, 'id') else "Unknown"
            print(f"\n🎉 GAME OVER! Winner: {winner_name}")
            print(f"🏆 Restarting server in {self.server.restart_delay} seconds...")

            restart_message = {
                'type': 'game_restarting',
                'winner': winner_name,
                'restart_delay': self.server.restart_delay,
                'message': f'Game finished! Winner: {winner_name}. Server restarting in {self.server.restart_delay} seconds...'
            }
            data = pickle.dumps(restart_message, protocol=4)
            length_bytes = len(data).to_bytes(4, byteorder='big')

            for player_id, client_socket in self.server.clients.items():
                try:
                    self.server._send_data_safe(client_socket, length_bytes + data)
                except Exception as e:
                    print(f"Failed to send restart notification to {player_id}: {e}")

        current_lists = self._collect_current_entity_states()
        current_map = self._build_entity_map(current_lists)
        self.server.frame_counter += 1

        game_over = self.server.arena.game_over
        winner_id = None
        if game_over and self.server.arena.winner and hasattr(self.server.arena.winner, 'id'):
            winner_id = self.server.arena.winner.id

        static_update = (self.server.frame_counter % self.server.static_update_interval == 0)

        disconnected_clients = []
        for player_id, client_socket in list(self.server.clients.items()):
            try:
                if not self._client_supports_delta(player_id):
                    legacy_state = {
                        'type': 'game_state',
                        'timestamp': round(time.time(), 2),
                        'characters': current_lists['characters'],
                        'projectiles': current_lists['projectiles'],
                        'weapons': current_lists['weapons'],
                        'ammo_pickups': current_lists['ammo_pickups'],
                        'platforms': current_lists['platforms'],
                        'game_over': game_over,
                    }
                    if game_over and winner_id:
                        legacy_state['winner_id'] = winner_id

                    data = pickle.dumps(legacy_state, protocol=4)
                    length_bytes = len(data).to_bytes(4, byteorder='big')
                    self.server._send_data_safe(client_socket, length_bytes + data)
                    continue

                send_full = (
                    (self.server.frame_counter % self.server.full_state_interval == 0)
                    or player_id not in self.server.client_state_cache
                    or player_id in self.server.requested_full_state
                )

                if send_full:
                    self._send_full_state(player_id, client_socket, current_lists, current_map, game_over, winner_id)
                    continue

                payload, force_full, removed_ids = self._compute_delta_payload(
                    player_id,
                    current_lists,
                    current_map,
                    static_update,
                    game_over,
                    winner_id,
                )

                if force_full or payload is None:
                    self._send_full_state(player_id, client_socket, current_lists, current_map, game_over, winner_id)
                    continue

                self._send_delta_state(player_id, client_socket, payload, current_map, removed_ids, static_update)
            except Exception as e:
                print(f"Failed to send to {player_id}: {e}")
                disconnected_clients.append(player_id)

        for player_id in disconnected_clients:
            self.server._handle_client_disconnect(player_id)
