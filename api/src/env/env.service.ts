import { Injectable } from '@nestjs/common';
import { PythonEnvClient } from './python-env.client';
import { CreateEnvDto } from './dto/create-env.dto';
import { StepEnvDto } from './dto/step-env.dto';
import { ReplayService } from '../replay/replay.service';
import { LogService } from '../log/log.service';
import { ErrorCode } from '../common/error-codes';

interface PythonCreateResponse {
  env_id: string;
  state: Record<string, unknown>;
  seed?: number;
  ruleset_version?: string;
}

interface PythonStepResponse {
  state: Record<string, unknown>;
  reward: number;
  done: boolean;
  info: Record<string, unknown>;
}

@Injectable()
export class EnvService {
  constructor(
    private readonly pythonEnvClient: PythonEnvClient,
    private readonly replayService: ReplayService,
    private readonly logService: LogService,
  ) {}

  async createEnvironment(dto: CreateEnvDto, requestId?: string) {
    try {
      const payload = {
        seed: dto.seed,
        ruleset_version: dto.rulesetVersion,
      };
      const response = (await this.pythonEnvClient.createEnvironment(payload)) as PythonCreateResponse;
      const envId = response.env_id;
      await this.replayService.createOrResetReplay(
        envId,
        response.seed?.toString(),
        response.ruleset_version,
        response.state,
      );
      this.logService.log('info', 'Environment created', { envId }, requestId);
      return {
        envId,
        state: response.state,
        seed: response.seed ?? dto.seed,
        rulesetVersion: response.ruleset_version ?? dto.rulesetVersion,
      };
    } catch (error) {
      this.logService.log('error', 'Failed to create environment', { error: this.serializeError(error) }, requestId);
      return { error: ErrorCode.ERR_INTERNAL };
    }
  }

  async stepEnvironment(dto: StepEnvDto, requestId?: string) {
    try {
      const payload = { env_id: dto.envId, action: dto.action };
      const response = (await this.pythonEnvClient.step(payload)) as PythonStepResponse;
      await this.replayService.appendStep(dto.envId, dto.action ?? null, response.state);
      this.logService.log('info', 'Environment step', { envId: dto.envId }, requestId);
      return {
        envId: dto.envId,
        state: response.state,
        reward: response.reward,
        done: response.done,
        info: response.info,
      };
    } catch (error) {
      this.logService.log('error', 'Failed to step environment', { envId: dto.envId, error: this.serializeError(error) }, requestId);
      return { error: ErrorCode.ERR_INTERNAL };
    }
  }

  async legalActions(envId: string, requestId?: string) {
    try {
      const response = await this.pythonEnvClient.legalActions(envId);
      this.logService.log('debug', 'Fetched legal actions', { envId }, requestId);
      return { envId, actions: response.actions ?? [] };
    } catch (error) {
      this.logService.log('error', 'Failed to fetch legal actions', { envId, error: this.serializeError(error) }, requestId);
      return { error: ErrorCode.ERR_INTERNAL };
    }
  }

  async fetchReplay(envId: string, requestId?: string) {
    try {
      const replay = await this.replayService.findByEnvId(envId);
      if (!replay) {
        this.logService.log('warn', 'Replay not found for env', { envId }, requestId);
        return { error: ErrorCode.ERR_REPLAY_NOT_FOUND };
      }
      return replay;
    } catch (error) {
      this.logService.log('error', 'Failed to fetch replay', { envId, error: this.serializeError(error) }, requestId);
      return { error: ErrorCode.ERR_INTERNAL };
    }
  }

  private serializeError(error: unknown) {
    if (error instanceof Error) {
      return { message: error.message, stack: error.stack };
    }
    return { error };
  }
}
