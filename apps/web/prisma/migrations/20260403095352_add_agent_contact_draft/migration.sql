-- CreateTable
CREATE TABLE "AgentContactDraft" (
    "id" TEXT NOT NULL,
    "agentCandidateId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "campaignId" TEXT,
    "name" TEXT NOT NULL,
    "firstName" TEXT,
    "lastName" TEXT,
    "email" TEXT,
    "title" TEXT,
    "specialty" TEXT,
    "city" TEXT,
    "contactType" TEXT NOT NULL,
    "isTested" BOOLEAN NOT NULL DEFAULT false,
    "sourceStage" TEXT NOT NULL,
    "sourceTool" TEXT,
    "sourceUrl" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "AgentContactDraft_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AgentContactDraft_agentCandidateId_idx" ON "AgentContactDraft"("agentCandidateId");

-- CreateIndex
CREATE INDEX "AgentContactDraft_userId_idx" ON "AgentContactDraft"("userId");

-- CreateIndex
CREATE INDEX "AgentContactDraft_campaignId_idx" ON "AgentContactDraft"("campaignId");

-- AddForeignKey
ALTER TABLE "AgentContactDraft" ADD CONSTRAINT "AgentContactDraft_agentCandidateId_fkey" FOREIGN KEY ("agentCandidateId") REFERENCES "AgentCandidate"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentContactDraft" ADD CONSTRAINT "AgentContactDraft_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentContactDraft" ADD CONSTRAINT "AgentContactDraft_campaignId_fkey" FOREIGN KEY ("campaignId") REFERENCES "Campaign"("id") ON DELETE CASCADE ON UPDATE CASCADE;
