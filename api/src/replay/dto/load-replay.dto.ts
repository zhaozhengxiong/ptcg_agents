import { IsNotEmpty, IsString } from 'class-validator';

export class LoadReplayDto {
  @IsString()
  @IsNotEmpty()
  replayId!: string;
}
