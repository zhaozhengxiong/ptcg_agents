import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { EnvController } from './env.controller';
import { EnvService } from './env.service';
import { PythonEnvClient } from './python-env.client';
import { ReplayModule } from '../replay/replay.module';
import { LogModule } from '../log/log.module';

@Module({
  imports: [HttpModule, ReplayModule, LogModule],
  controllers: [EnvController],
  providers: [EnvService, PythonEnvClient],
})
export class EnvModule {}
