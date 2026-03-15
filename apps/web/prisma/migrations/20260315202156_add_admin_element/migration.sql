-- AlterTable
ALTER TABLE "AppConfig" ADD COLUMN     "filterBatchSize" INTEGER NOT NULL DEFAULT 1,
ADD COLUMN     "modelFilter" TEXT NOT NULL DEFAULT 'sonar-pro';
