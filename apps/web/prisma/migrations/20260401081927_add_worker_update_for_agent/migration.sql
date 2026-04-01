/*
  Warnings:

  - A unique constraint covering the columns `[jobId,domain]` on the table `AgentCandidate` will be added. If there are existing duplicate values, this will fail.

*/
-- DropIndex
DROP INDEX "AgentCandidate_userId_domain_key";

-- AlterTable
ALTER TABLE "AgentCandidate" ADD COLUMN     "jobId" TEXT;

-- AlterTable
ALTER TABLE "Job" ADD COLUMN     "cancelRequestedAt" TIMESTAMP(3),
ADD COLUMN     "type" TEXT NOT NULL DEFAULT 'campaign_generate',
ALTER COLUMN "campaignId" DROP NOT NULL;

-- CreateIndex
CREATE INDEX "AgentCandidate_campaignId_status_idx" ON "AgentCandidate"("campaignId", "status");

-- CreateIndex
CREATE INDEX "AgentCandidate_jobId_status_idx" ON "AgentCandidate"("jobId", "status");

-- CreateIndex
CREATE UNIQUE INDEX "AgentCandidate_jobId_domain_key" ON "AgentCandidate"("jobId", "domain");

-- AddForeignKey
ALTER TABLE "AgentCandidate" ADD CONSTRAINT "AgentCandidate_campaignId_fkey" FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentCandidate" ADD CONSTRAINT "AgentCandidate_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;
