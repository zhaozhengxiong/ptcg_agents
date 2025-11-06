import { Controller, Get, Param, Post, Body } from '@nestjs/common';
import { ReplayService } from './replay.service';
import { LoadReplayDto } from './dto/load-replay.dto';
import { StepReplayDto } from './dto/step-replay.dto';
import { buildErrorResponse, buildSuccessResponse } from '../common/api-response';
import { ErrorCode } from '../common/error-codes';

@Controller('replay')
export class ReplayController {
  constructor(private readonly replayService: ReplayService) {}

  @Post('load')
  async loadReplay(@Body() dto: LoadReplayDto) {
    const { replay, steps, error } = await this.replayService.loadReplay(dto.replayId);
    if (error) {
      return buildErrorResponse(error, 'Replay not found', null);
    }
    return buildSuccessResponse({ replay, steps }, 'replay loaded');
  }

  @Post('step')
  async stepReplay(@Body() dto: StepReplayDto) {
    const { step, nextCursor, total, error } = await this.replayService.stepReplay(
      dto.replayId,
      dto.cursor ?? 0,
    );
    if (error) {
      const message = error === ErrorCode.ERR_REPLAY_NOT_FOUND ? 'Replay not found' : 'Cursor out of range';
      return buildErrorResponse(error, message, null);
    }
    return buildSuccessResponse({ step, nextCursor, total }, 'replay step');
  }

  @Get('render/:replayId')
  async renderReplay(@Param('replayId') replayId: string) {
    const replay = await this.replayService.findById(replayId);
    if (!replay) {
      return buildErrorResponse(ErrorCode.ERR_REPLAY_NOT_FOUND, 'Replay not found', null);
    }
    return buildSuccessResponse(replay, 'replay render snapshot');
  }
}
