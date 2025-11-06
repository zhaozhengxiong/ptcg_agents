import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { EnvModule } from './env/env.module';
import { ReplayModule } from './replay/replay.module';
import { LogModule } from './log/log.module';
import { ReplayEntity } from './replay/replay.entity';
import { RequestIdMiddleware } from './common/request-context';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: async (configService: ConfigService) => ({
        type: 'postgres',
        host: configService.get('POSTGRES_HOST', 'localhost'),
        port: parseInt(configService.get('POSTGRES_PORT', '5432'), 10),
        username: configService.get('POSTGRES_USER', 'postgres'),
        password: configService.get('POSTGRES_PASSWORD', 'postgres'),
        database: configService.get('POSTGRES_DB', 'ptcg'),
        autoLoadEntities: true,
        synchronize: configService.get('TYPEORM_SYNC', 'true') === 'true',
        logging: configService.get('TYPEORM_LOGGING', 'false') === 'true',
      }),
    }),
    TypeOrmModule.forFeature([ReplayEntity]),
    EnvModule,
    ReplayModule,
    LogModule,
  ],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer.apply(RequestIdMiddleware).forRoutes('*');
  }
}
