import { IsInt, IsNotEmpty, IsOptional, IsString, Min } from 'class-validator';

export class StepReplayDto {
  @IsString()
  @IsNotEmpty()
  replayId!: string;

  @IsOptional()
  @IsInt()
  @Min(0)
  cursor?: number;
}
