import { Body, Controller, Get, Post, Query, Req } from '@nestjs/common';
import { Request } from 'express';
import { EnvService } from './env.service';
import { CreateEnvDto } from './dto/create-env.dto';
import { StepEnvDto } from './dto/step-env.dto';
import { LegalActionsDto } from './dto/legal-actions.dto';
import { buildErrorResponse, buildSuccessResponse } from '../common/api-response';
import { ErrorCode } from '../common/error-codes';

@Controller('env')
export class EnvController {
  constructor(private readonly envService: EnvService) {}

  @Post('create')
  async create(@Body() dto: CreateEnvDto, @Req() req: Request) {
    const result = await this.envService.createEnvironment(dto, (req as any).requestId);
    if ('error' in result && result.error) {
      return buildErrorResponse(result.error, 'Failed to create environment', null, (req as any).requestId);
    }
    return buildSuccessResponse(result, 'environment created', (req as any).requestId);
  }

  @Post('step')
  async step(@Body() dto: StepEnvDto, @Req() req: Request) {
    const result = await this.envService.stepEnvironment(dto, (req as any).requestId);
    if ('error' in result && result.error) {
      return buildErrorResponse(result.error, 'Failed to step environment', null, (req as any).requestId);
    }
    return buildSuccessResponse(result, 'environment stepped', (req as any).requestId);
  }

  @Get('legal_actions')
  async legalActions(@Query() query: LegalActionsDto, @Req() req: Request) {
    const result = await this.envService.legalActions(query.envId, (req as any).requestId);
    if ('error' in result && result.error) {
      return buildErrorResponse(result.error, 'Failed to fetch legal actions', [], (req as any).requestId);
    }
    return buildSuccessResponse(result, 'legal actions fetched', (req as any).requestId);
  }

  @Get('replay')
  async replay(@Query('envId') envId: string, @Req() req: Request) {
    if (!envId) {
      return buildErrorResponse(ErrorCode.ERR_ENV_NOT_FOUND, 'envId is required', null, (req as any).requestId);
    }
    const result = await this.envService.fetchReplay(envId, (req as any).requestId);
    if ('error' in result && result.error) {
      const message = result.error === ErrorCode.ERR_REPLAY_NOT_FOUND ? 'Replay not found' : 'Failed to fetch replay';
      return buildErrorResponse(result.error, message, null, (req as any).requestId);
    }
    return buildSuccessResponse(result, 'replay fetched', (req as any).requestId);
  }
}
