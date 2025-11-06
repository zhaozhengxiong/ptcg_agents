import { Controller, Get, Query } from '@nestjs/common';
import { LogService } from './log.service';
import { buildSuccessResponse } from '../common/api-response';

@Controller('log')
export class LogController {
  constructor(private readonly logService: LogService) {}

  @Get()
  getRecent(@Query('limit') limit?: number) {
    const value = typeof limit === 'number' ? limit : limit ? parseInt(String(limit), 10) : undefined;
    const logs = this.logService.getRecent(value ?? 50);
    return buildSuccessResponse(logs, 'logs fetched');
  }
}
