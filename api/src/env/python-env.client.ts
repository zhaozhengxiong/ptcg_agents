import { HttpService } from '@nestjs/axios';
import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

@Injectable()
export class PythonEnvClient {
  private readonly logger = new Logger(PythonEnvClient.name);
  private readonly baseUrl: string;

  constructor(private readonly http: HttpService, configService: ConfigService) {
    this.baseUrl = configService.get('PYTHON_ENV_BASE_URL', 'http://localhost:8000');
  }

  async createEnvironment(payload: Record<string, unknown>) {
    return this.post('/env/create', payload);
  }

  async step(payload: Record<string, unknown>) {
    return this.post('/env/step', payload);
  }

  async legalActions(envId: string) {
    return this.get('/env/legal_actions', { envId });
  }

  async fetchReplay(envId: string) {
    return this.get('/env/replay', { envId });
  }

  private async post(path: string, payload: Record<string, unknown>) {
    try {
      const response = await firstValueFrom(this.http.post(`${this.baseUrl}${path}`, payload));
      return response.data;
    } catch (error) {
      this.logger.error(`PythonEnvClient POST ${path} failed`, error instanceof Error ? error.stack : undefined);
      throw error;
    }
  }

  private async get(path: string, params: Record<string, unknown>) {
    try {
      const response = await firstValueFrom(this.http.get(`${this.baseUrl}${path}`, { params }));
      return response.data;
    } catch (error) {
      this.logger.error(`PythonEnvClient GET ${path} failed`, error instanceof Error ? error.stack : undefined);
      throw error;
    }
  }
}
