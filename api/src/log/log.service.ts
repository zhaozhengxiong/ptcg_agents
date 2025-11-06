import { Injectable, Logger } from '@nestjs/common';

export interface LogEntry {
  timestamp: Date;
  level: 'debug' | 'info' | 'warn' | 'error';
  message: string;
  context?: Record<string, unknown>;
  requestId?: string;
}

@Injectable()
export class LogService {
  private readonly logger = new Logger('PTCG');
  private readonly entries: LogEntry[] = [];

  log(level: LogEntry['level'], message: string, context?: Record<string, unknown>, requestId?: string) {
    const entry: LogEntry = { timestamp: new Date(), level, message, context, requestId };
    this.entries.push(entry);
    switch (level) {
      case 'debug':
        this.logger.debug(message, JSON.stringify({ context, requestId }));
        break;
      case 'info':
        this.logger.log(message, JSON.stringify({ context, requestId }));
        break;
      case 'warn':
        this.logger.warn(message, JSON.stringify({ context, requestId }));
        break;
      case 'error':
        this.logger.error(message, JSON.stringify({ context, requestId }));
        break;
      default:
        this.logger.log(message, JSON.stringify({ context, requestId }));
    }
  }

  getRecent(limit = 50): LogEntry[] {
    return this.entries.slice(-limit);
  }
}
