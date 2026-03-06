-- AlterTable
ALTER TABLE "Campaign" ADD COLUMN     "dailyLimit" INTEGER,
ADD COLUMN     "launchedAt" TIMESTAMP(3),
ADD COLUMN     "sendEndHour" INTEGER DEFAULT 18,
ADD COLUMN     "sendStartHour" INTEGER DEFAULT 8,
ADD COLUMN     "sentCount" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "totalEmails" INTEGER;
