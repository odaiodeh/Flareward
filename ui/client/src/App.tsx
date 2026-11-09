import React, { useEffect } from "react";
import { Route, Switch, useRoute } from "wouter";
import AgenticOverview from "@/pages/AgenticOverview";
import Configuration from "@/pages/Configuration";
import AgentRepository from "@/pages/AgentRepository";
import AgenticChats from "@/pages/AgenticChats";

import AgenticTemplates from "@/pages/AgenticTemplates";
import ScheduledWorkflows from "@/pages/ScheduledWorkflows";
import HumanReviews from "@/pages/HumanReviews";
import Programs from "@/pages/Programs";
import Execution from "@/pages/Execution";
import GetToKnow from "@/pages/GetToKnow";
import Analytics from "@/pages/Analytics";
import NotFound from "@/pages/not-found";
import Login from "@/pages/Login";
import { ProjectProvider } from '@/contexts/ProjectContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { SharedProvider } from '@/contexts/SharedContext';
import { ViewProvider, useView } from '@/contexts/ViewContext';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { AgenticAIProvider } from '@/contexts/AgenticAIContext';
import { useTheme } from '@/contexts/ThemeContext';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import TermsApproval from '@/components/auth/TermsApproval';
import PublicChat from "./components/agentic-ai/chat/PublicChat";
import AgenticLayout from "./components/layout/AgenticLayout";
import { Toaster } from "./components/ui/toaster";

function AppRoutes() {
  const { viewMode } = useView();
  const [isChat] = useRoute("/chat/:token");
  const [isAgenticOverview] = useRoute("/agentic-overview");
  const [isInventory] = useRoute("/inventory");
  const [isAgenticChats] = useRoute("/agentic-chats");
  const [isAgenticChatsSession] = useRoute("/agentic-chats/:sessionId");
  const [isTemplates] = useRoute("/templates");
  const [isScheduledWorkflows] = useRoute("/scheduled-workflows");
  const [isReviews] = useRoute("/reviews");
  const [isReview] = useRoute("/reviews/:reviewId");
  const [isPrograms] = useRoute("/programs");
  const [isExecution] = useRoute("/executions/:executionId");

  const isAgenticRoute = isAgenticOverview || isInventory || isAgenticChats || isAgenticChatsSession || isTemplates || isScheduledWorkflows || isReviews || isReview || isPrograms || isExecution;

  if (isChat) {
    return (
      <AgenticAIProvider>
        <Route path="/chat/:token" component={PublicChat} />
      </AgenticAIProvider>
    );
  }

  if (isAgenticRoute) {
    return (
      <AgenticLayout>
        <AgenticAIProvider>
          <Switch>
            <Route path="/agentic-overview" component={AgenticOverview} />
            <Route path="/inventory" component={AgentRepository} />
            <Route path="/agentic-chats/:sessionId" component={AgenticChats} />
            <Route path="/agentic-chats" component={AgenticChats} />
            <Route path="/scheduled-workflows" component={ScheduledWorkflows} />
            <Route path="/reviews/:reviewId" component={HumanReviews} />
            <Route path="/reviews" component={HumanReviews} />
            <Route path="/programs" component={Programs} />
            <Route path="/executions/:executionId" component={Execution} />
            <Route path="/templates" component={AgenticTemplates} />
          </Switch>
        </AgenticAIProvider>
      </AgenticLayout>
    );
  }


  return (
    <Switch>
      <Route path="/" component={GetToKnow} />
      <Route path="/get-to-know" component={GetToKnow} />
      <Route path="/configuration" component={Configuration} />
      <Route path="/analytics" component={Analytics} />
      <Route component={NotFound} />
    </Switch>
  );
}

/** /login outside ProtectedRoute; use full navigation (no wouter setLocation) to match app routing convention. */
function LoginRouteContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const { primaryHex } = useTheme();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      window.location.replace('/');
    }
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0D1117]">
        <div
          className="animate-spin rounded-full h-12 w-12 border-b-2"
          style={{ borderBottomColor: primaryHex || "#A60000" }}
        />
      </div>
    );
  }

  if (isAuthenticated) {
    return null;
  }

  return <Login />;
}

function AppContent() {
  return (
    <Switch>
      <Route path="/login">
        <LoginRouteContent />
      </Route>
      <Route>
        <ProtectedRoute>
          <TermsApproval>
            <AppRoutes />
          </TermsApproval>
        </ProtectedRoute>
      </Route>
    </Switch>
  );
}

/** Resource, notification and sharing state belong to one authenticated workspace. */
function WorkspaceContent() {
  const { viewMode, selectedTeam } = useView();
  const { user } = useAuth();
  const workspaceKey = JSON.stringify([user?.username, viewMode, viewMode === 'team' ? selectedTeam?.id : null]);
  return (
    <SharedProvider key={workspaceKey}>
      <ProjectProvider>
        <NotificationProvider>
          <AppContent />
        </NotificationProvider>
      </ProjectProvider>
    </SharedProvider>
  );
}

function App() {
  // Set document title
  useEffect(() => {
    document.title = "Flareward";
  }, []);

  return (
    <ThemeProvider>
      <AuthProvider>
        <ViewProvider>
          <WorkspaceContent />
        </ViewProvider>
      </AuthProvider>
      <Toaster />
    </ThemeProvider>
  );
}

export default App;

