-- AlterTable
ALTER TABLE "User" ADD COLUMN     "role" TEXT NOT NULL DEFAULT 'user';

-- CreateTable
CREATE TABLE "AppConfig" (
    "id" TEXT NOT NULL DEFAULT 'singleton',
    "maxConcurrent" INTEGER NOT NULL DEFAULT 2,
    "batchSize" INTEGER NOT NULL DEFAULT 3,
    "pollIntervalMs" INTEGER NOT NULL DEFAULT 15000,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AppConfig_pkey" PRIMARY KEY ("id")
);
