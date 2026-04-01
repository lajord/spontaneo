-- CreateTable
CREATE TABLE "AgentContact" (
    "id" TEXT NOT NULL,
    "agentCandidateId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "firstName" TEXT,
    "lastName" TEXT,
    "email" TEXT,
    "title" TEXT,
    "phone" TEXT,
    "linkedin" TEXT,
    "emailStatus" TEXT,
    "source" TEXT,
    "qualityScore" INTEGER,
    "qualityReason" TEXT,
    "isDecisionMaker" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AgentContact_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "AgentContact_userId_idx" ON "AgentContact"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "AgentContact_agentCandidateId_email_key" ON "AgentContact"("agentCandidateId", "email");

-- AddForeignKey
ALTER TABLE "AgentContact" ADD CONSTRAINT "AgentContact_agentCandidateId_fkey" FOREIGN KEY ("agentCandidateId") REFERENCES "AgentCandidate"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AgentContact" ADD CONSTRAINT "AgentContact_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
