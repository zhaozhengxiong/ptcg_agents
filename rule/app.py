"""FastAPI application exposing the SimpleEnv over HTTP for the NestJS API."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from env.simple_env import SimpleEnv


@dataclass
class EnvironmentSession:
    """Tracks a running environment instance and its replay information."""

    env: SimpleEnv
    seed: Optional[int]
    ruleset_version: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    states: List[Dict[str, Any]] = field(default_factory=list)
    state_hashes: List[str] = field(default_factory=list)

    def record_state(self, state: Dict[str, Any]) -> None:
        self.states.append(state)
        serialised = json.dumps(state, sort_keys=True, separators=(",", ":"))
        self.state_hashes.append(sha256(serialised.encode("utf-8")).hexdigest())


class CreateEnvRequest(BaseModel):
    seed: Optional[int] = Field(default=None, description="Randomness seed for the environment")
    ruleset_version: str = Field(default="v0", description="Ruleset version identifier")


class CreateEnvResponse(BaseModel):
    env_id: str
    state: Dict[str, Any]
    seed: Optional[int]
    ruleset_version: str


class StepRequest(BaseModel):
    env_id: str
    action: Optional[Dict[str, Any]] = None


class StepResponse(BaseModel):
    state: Dict[str, Any]
    reward: float
    done: bool
    info: Dict[str, Any]


class ReplayResponse(BaseModel):
    env_id: str
    seed: Optional[int]
    ruleset_version: str
    actions: List[Dict[str, Any]]
    states: List[Dict[str, Any]]
    state_hashes: List[str]


class LegalActionsResponse(BaseModel):
    env_id: str
    actions: List[Dict[str, Any]]


class EnvironmentManager:
    """In-memory registry of running environments."""

    def __init__(self) -> None:
        self._sessions: Dict[str, EnvironmentSession] = {}

    def create(self, seed: Optional[int], ruleset_version: str) -> CreateEnvResponse:
        env_id = str(uuid4())
        env = SimpleEnv(seed=seed)
        session = EnvironmentSession(env=env, seed=seed, ruleset_version=ruleset_version)
        initial_state = env.reset()
        session.record_state(initial_state)
        self._sessions[env_id] = session
        return CreateEnvResponse(
            env_id=env_id,
            state=initial_state,
            seed=seed,
            ruleset_version=ruleset_version,
        )

    def require_session(self, env_id: str) -> EnvironmentSession:
        if env_id not in self._sessions:
            raise HTTPException(status_code=404, detail="Environment not found")
        return self._sessions[env_id]

    def step(self, env_id: str, action: Optional[Dict[str, Any]]) -> StepResponse:
        session = self.require_session(env_id)
        result = session.env.step(action)
        session.actions.append(action or {})
        session.record_state(result.state)
        return StepResponse(
            state=result.state,
            reward=result.reward,
            done=result.done,
            info=result.info,
        )

    def legal_actions(self, env_id: str) -> LegalActionsResponse:
        session = self.require_session(env_id)
        if session.env.done:
            actions: List[Dict[str, Any]] = []
        else:
            actions = [{"type": "noop"}]
        return LegalActionsResponse(env_id=env_id, actions=actions)

    def replay(self, env_id: str) -> ReplayResponse:
        session = self.require_session(env_id)
        return ReplayResponse(
            env_id=env_id,
            seed=session.seed,
            ruleset_version=session.ruleset_version,
            actions=session.actions,
            states=session.states,
            state_hashes=session.state_hashes,
        )


manager = EnvironmentManager()
app = FastAPI(title="PTCG Rule Service", version="0.1.0")


@app.get("/healthz")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/env/create", response_model=CreateEnvResponse)
def create_env(payload: CreateEnvRequest) -> CreateEnvResponse:
    return manager.create(seed=payload.seed, ruleset_version=payload.ruleset_version)


@app.post("/env/step", response_model=StepResponse)
def step_env(payload: StepRequest) -> StepResponse:
    return manager.step(env_id=payload.env_id, action=payload.action)


@app.get("/env/legal_actions", response_model=LegalActionsResponse)
def legal_actions(envId: str) -> LegalActionsResponse:
    return manager.legal_actions(env_id=envId)


@app.get("/env/replay", response_model=ReplayResponse)
def get_replay(envId: str) -> ReplayResponse:
    return manager.replay(env_id=envId)
