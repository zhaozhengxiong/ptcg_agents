import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ReplayEntity } from './replay.entity';
import { ReplayService } from './replay.service';
import { ReplayController } from './replay.controller';
import { LogModule } from '../log/log.module';

@Module({
  imports: [TypeOrmModule.forFeature([ReplayEntity]), LogModule],
  providers: [ReplayService],
  controllers: [ReplayController],
  exports: [ReplayService],
})
export class ReplayModule {}
