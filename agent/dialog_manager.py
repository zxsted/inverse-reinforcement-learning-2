"""Handcrafted dialog policy for the dialog manager."""

from agent_action import AgentActions
from agent_state import AgentState
from utils.params import AGENT_EXPLICIT_VS_IMPLICIT_CONFIRMATION_PROBABILITY
from utils.params import AgentActionType
from utils.params import AgentStateStatus
from utils.params import UserActionType
from utils.params import NUM_SLOTS

from numpy.random import binomial


class DialogManager:
    def __init__(self, init_state=AgentState()):
        self.state = init_state
        self.prev_agent_act = None

    def start_dialog(self):
        # print("Agent-- [State] " + str(self.state))
        # Agent starts with a GREETING
        self.prev_agent_act = AgentActions.greet.value
        print("Agent-- (Action) " + str(self.prev_agent_act))
        return self.prev_agent_act

    def take_turn(self, user_act):
        """Executes an agent turn based on the user's most recent action.

        Args:
            user_act (UserAction): User's most recent action.

        Returns:
            AgentAction: Agent's next action.
        """
        next_action = self.update_state_and_next_action(user_act)
        self.prev_agent_act = next_action
        # print("Agent-- [State] " + str(self.state))
        print("Agent-- (Action) " + str(next_action))
        return next_action

    def update_state_and_next_action(self, user_act):
        """Updates the agent's state and returns the next action for the agent,
        given the dialog history and the current user-action.

        Args:
            user_act (UserAction): Current user-action.

        Returns:
            AgentAction: Next action to be taken by the agent.

        Raises:
            ValueError: Unhandled user-action in a given scenario.
        """

        # If the agent greeted, and the user remains silent, then ask for a
        # slot. However, if the user responded with information for all slots,
        # mark all the slots as "OBTAINED", and move to confirmation.
        if self.prev_agent_act.type is AgentActionType.GREET:
            if user_act.type is UserActionType.SILENT:
                return self._ask_confirm_or_close()
            elif user_act.type is UserActionType.ALL_SLOTS:
                self._mark_all_slots_as_obtained()
                return self._ask_confirm_or_close()

        # If the agent requested a slot, and the user provided one or more
        # slots, then mark those slots as PROVIDED, and move to confirmation.
        if self.prev_agent_act.type is AgentActionType.ASK_SLOT:
            if user_act.type is UserActionType.ONE_SLOT:
                self.state.mark_slot_as_obtained(self.prev_agent_act.ask_id)
                return self._confirm()
            elif user_act.type is UserActionType.ALL_SLOTS:
                self._mark_all_slots_as_obtained()
                return self._ask_confirm_or_close()
            else:
                raise ValueError("User-act of type {} is not supported when"
                                 "previous agent act was {}"
                                 .format(user_act.type.value,
                                         self.prev_agent_act.type.value))

        # If the agent requested an explicit confirmation, then update the slot
        # based on whether the user agrees or dissents. Follow this with a
        # request for another slot, or close dialog, as appropriate.
        if self.prev_agent_act.type is AgentActionType.EXPLICIT_CONFIRM:
            if user_act.type is UserActionType.CONFIRM:
                self.state.mark_slot_as_confirmed(
                    self.prev_agent_act.confirm_id)
                return self._ask_confirm_or_close()
            elif user_act.type is UserActionType.NEGATE:
                self.state.mark_slot_as_empty(self.prev_agent_act.confirm_id)
                return self._ask_confirm_or_close()
            else:
                raise ValueError("User-act of type {} is not supported when"
                                 "previous agent act was {}"
                                 .format(user_act.type.value,
                                         self.prev_agent_act.type.value))

        # Implicit confirmation involves a confirmation for a previously
        # requested slot along with a new request for another slot.
        # If the agent went for an implicit confirmation at the last step, then
        # update the slot being confirmed as per the user-response: Negation
        # should result in the slot being marked EMPTY, while user's act of
        # providing information for the requested slot should be treated as an
        # affirmation for the slot being confirmed.
        if self.prev_agent_act.type is AgentActionType.CONFIRM_ASK:
            if user_act.type is UserActionType.ONE_SLOT:
                # Mark the slot for which implicit confirmation was requested
                # as "CONFIRMED".
                self.state.mark_slot_as_confirmed(
                    self.prev_agent_act.confirm_id)
                # Update the slot for which the user provided information.
                self.state.mark_slot_as_obtained(self.prev_agent_act.ask_id)
                return self._confirm()
            elif user_act.type is UserActionType.NEGATE:
                self.state.mark_slot_as_empty(self.prev_agent_act.confirm_id)
                return self._ask_confirm_or_close()
            else:
                raise ValueError("User-act of type {} is not supported when"
                                 "previous agent act was {}"
                                 .format(user_act.type.value,
                                         self.prev_agent_act.type.value))

        # If the user wants to end the conversation, the agent should oblidge.
        if user_act.type is UserActionType.CLOSE:
            return AgentActions.close.value

    def _mark_all_slots_as_obtained(self):
        for id_ in xrange(NUM_SLOTS):
            if self.state.slots[id_] is AgentStateStatus.EMPTY:
                self.state.mark_slot_as_obtained(id_)

    def _ask_or_close(self):
        slot_id = self.state.get_empty_slot()
        if slot_id is None:
            return AgentActions.close.value
        else:
            return AgentActions.ask_slot.value[slot_id]

    def _ask_confirm_or_close(self):
        empty_slot_id = self.state.get_empty_slot()
        if empty_slot_id is None:
            unconfirmed_slot_id = self.state.get_unconfirmed_slot()
            if unconfirmed_slot_id is None:
                return AgentActions.close.value
            else:
                return AgentActions.explicit_confirm.value[unconfirmed_slot_id]
        else:
            return AgentActions.ask_slot.value[empty_slot_id]

    def _confirm(self):
        # Controls the fraction of total confirmations that are explicit.
        b = binomial(1, AGENT_EXPLICIT_VS_IMPLICIT_CONFIRMATION_PROBABILITY)
        if b == 1:
            return self._explicit_confirm()
        else:
            return self._implicit_confirm()

    def _explicit_confirm(self):
        return AgentActions.explicit_confirm.value[self.prev_agent_act.ask_id]

    def _implicit_confirm(self):
        empty_slot_id = self.state.get_empty_slot()
        confirm_slot_id = self.prev_agent_act.ask_id
        if empty_slot_id is None:
            return AgentActions.explicit_confirm.value[confirm_slot_id]
        else:
            return (AgentActions.confirm_ask
                    .value[confirm_slot_id][empty_slot_id])
