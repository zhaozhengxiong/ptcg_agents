import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ReplayEntity } from './replay.entity';
import { createHash } from 'crypto';
import { LogService } from '../log/log.service';
import { ErrorCode } from '../common/error-codes';

export interface ReplayStep {
  action: Record<string, unknown> | null;
  state: Record<string, unknown>;
  stateHash: string;
}

@Injectable()
export class ReplayService {
  constructor(
    @InjectRepository(ReplayEntity) private readonly replayRepository: Repository<ReplayEntity>,
    private readonly logService: LogService,
  ) {}

  async createOrResetReplay(envId: string, seed?: string, rulesetVersion?: string, initialState?: Record<string, unknown>) {
    let replay = await this.replayRepository.findOne({ where: { envId } });
    if (!replay) {
      replay = this.replayRepository.create({ envId, seed, rulesetVersion, actions: [], states: [], stateHashes: [] });
    } else {
      replay.seed = seed;
      replay.rulesetVersion = rulesetVersion;
      replay.actions = [];
      replay.states = [];
      replay.stateHashes = [];
    }

    if (initialState) {
      const stateHash = this.computeStateHash(initialState);
      replay.states.push(initialState);
      replay.stateHashes.push(stateHash);
    }

    const saved = await this.replayRepository.save(replay);
    this.logService.log('info', 'Replay session initialised', { envId, replayId: saved.id }, undefined);
    return saved;
  }

  async appendStep(envId: string, action: Record<string, unknown> | null, state: Record<string, unknown>) {
    const replay = await this.replayRepository.findOne({ where: { envId } });
    if (!replay) {
      this.logService.log('warn', 'Attempted to append step to missing replay', { envId }, undefined);
      return null;
    }
    const stateHash = this.computeStateHash(state);
    replay.actions.push(action ?? null);
    replay.states.push(state);
    replay.stateHashes.push(stateHash);
    await this.replayRepository.save(replay);
    return { replayId: replay.id, stateHash };
  }

  async findByEnvId(envId: string) {
    return this.replayRepository.findOne({ where: { envId } });
  }

  async findById(id: string) {
    return this.replayRepository.findOne({ where: { id } });
  }

  async loadReplay(id: string) {
    const replay = await this.findById(id);
    if (!replay) {
      return { error: ErrorCode.ERR_REPLAY_NOT_FOUND };
    }
    const steps: ReplayStep[] = replay.states.map((state, index) => ({
      state,
      stateHash: replay.stateHashes[index],
      action: index === 0 ? null : replay.actions[index - 1] ?? null,
    }));
    return { replay, steps };
  }

  async stepReplay(id: string, cursor = 0) {
    const replay = await this.findById(id);
    if (!replay) {
      return { error: ErrorCode.ERR_REPLAY_NOT_FOUND };
    }
    if (cursor < 0 || cursor >= replay.states.length) {
      return { error: ErrorCode.ERR_ILLEGAL_ACTION };
    }
    const step: ReplayStep = {
      state: replay.states[cursor],
      stateHash: replay.stateHashes[cursor],
      action: cursor === 0 ? null : replay.actions[cursor - 1] ?? null,
    };
    return { step, nextCursor: cursor + 1, total: replay.states.length };
  }

  computeStateHash(state: Record<string, unknown>): string {
    const payload = JSON.stringify(state ?? {});
    return createHash('sha256').update(payload).digest('hex');
  }
}
